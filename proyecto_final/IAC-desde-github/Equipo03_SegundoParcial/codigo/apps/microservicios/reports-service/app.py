"""
reports-service — generación, sellado y descarga de reportes.

Responsabilidad única: tomar resultados que YA están publicados y
convertirlos en un archivo que alguien se pueda llevar: CSV para la hoja de
cálculo, JSON para otro sistema, XML para el contrato del equipo.

Tres decisiones de diseño que vale la pena dejar escritas, porque las tres
se pueden hacer mal sin que se note:

1. NUNCA invoca agregado.fn_calcular_agregado_protegido. Un reporte no
   calcula un agregado nuevo: lee lo ya publicado. Si lo calculara,
   exportar un CSV gastaría presupuesto de épsilon, y bastarían unas
   cuantas descargas para dejar a la campaña sin poder publicar nada más.

2. Las filas suprimidas SE EXPORTAN, con su motivo y sin valor. Un CSV que
   las omitiera en silencio haría creer que la campaña tuvo menos unidades
   de las que tuvo, y exageraría la cobertura: quien lo lea sumaría 8 de 8
   unidades publicadas cuando en realidad fueron 8 de 12. La supresión es
   parte del resultado, no un hueco que haya que esconder.

3. Un reporte se sella y no se edita. Al generarlo se calcula el SHA-256
   del contenido canónico y se guarda con el documento. Si los datos
   cambian, se genera un reporte nuevo con su propio sello; el viejo sigue
   siendo la foto de lo que se vio ese día. Eso es lo que permite que un
   auditor confronte el archivo que le mandaron contra el sello que quedó
   registrado.

Dónde vive cada cosa: los datos se leen de PostgreSQL (las vistas de
resultados protegidos) y el reporte generado se guarda en MongoDB, porque
cada tipo de reporte tiene columnas distintas y un esquema fijo obligaría a
una tabla por tipo o a un modelo entidad-atributo-valor.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import os
import uuid

from flask import Response, g, request

from comun import (ErrorApi, VERSION_API, crear_servicio,
                   cuerpo_peticion, limite_consumo,
                   obtener_redis, pagina, quiere_xml, responder,
                   requiere_permiso, requiere_token, sobre_pagina, a_xml)
from comun.datos import consultar, cursor, ping as ping_pg
from comun.mongo import (ASCENDING, DESCENDING, asegurar_indices, base,
                         ping as ping_mongo, verificar_sin_identidad)

os.environ.setdefault("NOMBRE_SERVICIO", "reports-service")

# PDF y Excel los exige la especificacion del servicio. CSV se abre
# en Excel pero no es un archivo de Excel: no lleva tipos, ni anchos,
# ni formato, y quien lo recibe lo arregla a mano cada vez.
FORMATOS = ("json", "csv", "xml", "xlsx", "pdf")

# ---------------------------------------------------------------------------
# Catálogo de reportes.
#
# Cada tipo declara: el permiso que exige, la consulta (siempre sobre
# vistas o tablas de resultados ya publicados), el parámetro que admite y
# una nota que explica qué significan sus columnas. El catálogo es datos,
# no código: agregar un reporte es agregar una entrada, y la validación, el
# sellado, la paginación y los tres formatos de salida ya aplican solos.
# ---------------------------------------------------------------------------
CATALOGO = {
    "TABLERO_CAMPANIA": {
        "permisos": ("AGREGADO_UNIDAD", "AGREGADO_GLOBAL"),
        "titulo": "Resultados protegidos por unidad y dimensión",
        "parametro": "campania_id",
        "parametro_obligatorio": True,
        "nota": "Incluye las filas suprimidas con estado_publicacion=SUPRIMIDO y "
                "sin valor. El valor publicado trae ruido de Laplace: no es el "
                "promedio real de la unidad y no debe tratarse como tal.",
        "sql": "SELECT campania_id, unidad_organizacional_id, unidad, dimension, "
               "       estado_publicacion, participacion_protegida, "
               "       valor_protegido, epsilon_aplicado, mecanismo, "
               "       precision_advertencia "
               "  FROM agregado.v_tablero_unidad "
               " WHERE campania_id = %s "
               " ORDER BY unidad, dimension",
    },
    "PARTICIPACION": {
        "permisos": ("AGREGADO_UNIDAD", "AGREGADO_GLOBAL", "BITACORA_CONSULTAR"),
        "titulo": "Participación por unidad",
        "parametro": "campania_id",
        "parametro_obligatorio": False,
        "nota": "Son conteos de respuesta, no puntajes. La cobertura se calcula "
                "contra la plantilla declarada de la unidad.",
        "sql": "SELECT rp.campania_id, rp.unidad_organizacional_id, "
               "       uo.nombre AS unidad, MAX(rp.n_observaciones) AS respuestas, "
               "       uo.plantilla_declarada, "
               "       CASE WHEN uo.plantilla_declarada > 0 "
               "            THEN ROUND(100.0 * MAX(rp.n_observaciones) "
               "                       / uo.plantilla_declarada, 1) "
               "            ELSE NULL END AS cobertura_porcentaje "
               "  FROM agregado.resultado_protegido rp "
               "  JOIN organizacion.unidad_organizacional uo "
               "       USING (unidad_organizacional_id) "
               " WHERE (%s IS NULL OR rp.campania_id = %s) "
               " GROUP BY rp.campania_id, rp.unidad_organizacional_id, uo.nombre, "
               "          uo.plantilla_declarada "
               " ORDER BY rp.campania_id DESC, uo.nombre",
        "params": lambda v: (v, v),
    },
    "PRESUPUESTO_EPSILON": {
        "permisos": ("PARAMETRO_ADMIN", "AGREGADO_GLOBAL", "BITACORA_CONSULTAR"),
        "titulo": "Estado del presupuesto de privacidad",
        "parametro": None,
        "nota": "Épsilon consumido y disponible por campaña y unidad. Es el "
                "reporte que sostiene la afirmación de que el presupuesto se "
                "respeta: sin él, 'aplicamos privacidad diferencial' no se "
                "puede verificar.",
        "sql": "SELECT campania_id, unidad_organizacional_id, unidad, "
               "       epsilon_total, epsilon_consumido, epsilon_restante, "
               "       agotado, consultas_realizadas "
               "  FROM agregado.v_estado_presupuesto "
               " ORDER BY campania_id, unidad_organizacional_id",
    },
    "SUPRESIONES": {
        "permisos": ("PARAMETRO_ADMIN", "BITACORA_CONSULTAR", "AGREGADO_GLOBAL"),
        "titulo": "Agregados suprimidos y por qué",
        "parametro": "campania_id",
        "parametro_obligatorio": False,
        "nota": "La cuenta de lo que NO se publicó. Es el reporte que un comité "
                "de privacidad pide primero, porque una plataforma que nunca "
                "suprime nada no está protegiendo a nadie.",
        "sql": "SELECT rp.campania_id, rp.unidad_organizacional_id, "
               "       uo.nombre AS unidad, "
               "       COALESCE(d.nombre, 'Indice global') AS dimension, "
               "       rp.estado_publicacion AS motivo_supresion, "
               "       rp.n_observaciones, rp.k_aplicado, "
               "       CASE rp.estado_publicacion "
               "            WHEN 'GRUPO_INSUFICIENTE' THEN "
               "                 'El grupo no alcanzo el umbral k: publicar el "
               "valor permitiria inferir respuestas individuales.' "
               "            WHEN 'PRESUPUESTO_PRIVACIDAD_AGOTADO' THEN "
               "                 'La campania agoto su presupuesto de epsilon: "
               "una consulta mas degradaria la garantia de privacidad.' "
               "            ELSE 'Motivo no clasificado.' END AS explicacion "
               "  FROM agregado.resultado_protegido rp "
               "  JOIN organizacion.unidad_organizacional uo "
               "       USING (unidad_organizacional_id) "
               "  LEFT JOIN catalogo.dimension d USING (dimension_id) "
               " WHERE rp.estado_publicacion <> 'PUBLICADO' "
               "   AND (%s IS NULL OR rp.campania_id = %s) "
               " ORDER BY rp.campania_id DESC, uo.nombre, dimension",
        "params": lambda v: (v, v),
    },
    "INTERVENCIONES": {
        "permisos": ("INTERVENCION_SEGUIMIENTO", "INTERVENCION_APROBAR",
                     "RECOMENDACION_CONSULTAR"),
        "titulo": "Planes de intervención y su seguimiento",
        "parametro": "unidad_organizacional_id",
        "parametro_obligatorio": False,
        "nota": "Una intervención es organizacional: aplica a una unidad, nunca "
                "a una persona. Por eso el reporte no trae responsables "
                "individuales de la unidad intervenida, solo quién respondió "
                "por el plan.",
        "sql": "SELECT p.intervencion_id, p.unidad_organizacional_id, "
               "       uo.nombre AS unidad, p.tipo_intervencion, p.estado, "
               "       p.fecha_inicio, p.fecha_fin, p.campania_linea_base, "
               "       count(s.seguimiento_id) AS seguimientos, "
               "       max(s.fecha_registro) AS ultimo_seguimiento "
               "  FROM intervencion.plan p "
               "  JOIN organizacion.unidad_organizacional uo "
               "       USING (unidad_organizacional_id) "
               "  LEFT JOIN intervencion.seguimiento s USING (intervencion_id) "
               " WHERE (%s IS NULL OR p.unidad_organizacional_id = %s) "
               " GROUP BY p.intervencion_id, p.unidad_organizacional_id, uo.nombre, "
               "          p.tipo_intervencion, p.estado, p.fecha_inicio, "
               "          p.fecha_fin, p.campania_linea_base "
               " ORDER BY p.fecha_inicio DESC",
        "params": lambda v: (v, v),
    },
    "BITACORA_AUDITORIA": {
        "permisos": ("BITACORA_CONSULTAR",),
        "titulo": "Bitácora de auditoría",
        "parametro": "accion",
        "parametro_obligatorio": False,
        "nota": "Quién hizo qué y con qué resultado. Se exporta el identificador "
                "del actor porque la rendición de cuentas de quien OPERA el "
                "sistema es lo contrario de la privacidad de quien RESPONDE: a "
                "un administrador que consulta agregados sensibles sí se le "
                "sigue el rastro.",
        "sql": "SELECT fecha_hora, actor_usuario_id, actor_perfil, accion, "
               "       tipo_recurso, recurso_id, resultado, correlacion_id "
               "  FROM auditoria.bitacora "
               " WHERE (%s IS NULL OR accion = %s) "
               " ORDER BY fecha_hora DESC "
               " LIMIT 5000",
        "params": lambda v: (v, v),
    },
    "RECOMENDACIONES": {
        "permisos": ("RECOMENDACION_CONSULTAR", "AGREGADO_UNIDAD",
                     "AGREGADO_GLOBAL"),
        "titulo": "Detecciones del motor de reglas y recomendaciones",
        "parametro": "campania_id",
        "parametro_obligatorio": False,
        "nota": "Cada detección es de una unidad y trae la explicación de la "
                "regla que la disparó. Una recomendación sin explicación no es "
                "accionable: nadie aprueba un plan porque un sistema lo diga.",
        "sql": "SELECT campania_id, unidad_organizacional_id, unidad, regla_id, "
               "       nivel, explicacion, tipo_intervencion, "
               "       intervencion_sugerida, orden "
               "  FROM riesgo.v_recomendaciones "
               " WHERE (%s IS NULL OR campania_id = %s) "
               " ORDER BY campania_id DESC, unidad, orden",
        "params": lambda v: (v, v),
    },
}

INDICES = {
    "reportes": [
        ([("reporte_id", ASCENDING)], {"unique": True, "name": "ix_reporte_id"}),
        ([("tipo", ASCENDING), ("fecha_generacion", DESCENDING)],
         {"name": "ix_tipo_fecha"}),
        ([("sello_sha256", ASCENDING)], {"name": "ix_sello"}),
        ([("generado_por", ASCENDING), ("fecha_generacion", DESCENDING)],
         {"name": "ix_actor_fecha"}),
    ],
}


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "reports-service",
    "Genera, sella y entrega reportes a partir de resultados ya publicados",
    comprobaciones={"postgresql": ping_pg, "mongodb": ping_mongo,
                    "redis": _ping_redis})

from comun import formatos as _formatos
from contrato import montar as _montar_contrato
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/reportes"


def _bitacora(accion, resultado, recurso=None):
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO auditoria.bitacora (actor_usuario_id, actor_perfil, "
                " accion, tipo_recurso, recurso_id, resultado, correlacion_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                ((g.get("actor") or {}).get("sub"),
                 ((g.get("actor") or {}).get("perfil") or "ANONIMO")[:30],
                 accion, "REPORTE", recurso, resultado,
                 getattr(g, "correlacion_id", "")))
    except Exception:
        app.logger.error("No se pudo escribir en la bitacora: %s", accion)


def _normalizar(valor):
    """Deja el valor listo para JSON, CSV y XML con la misma representación.

    Una fecha que en JSON sale como 2026-03-01T10:00:00 y en CSV como
    '2026-03-01 10:00:00' obligaría a quien compara los dos archivos a
    normalizar a mano, y el sello dejaría de servir para confrontarlos.
    """
    if isinstance(valor, (dt.datetime, dt.date)):
        return valor.isoformat()
    if isinstance(valor, dt.timedelta):
        return str(valor)
    if hasattr(valor, "normalize"):          # Decimal
        return float(valor)
    return valor


def _sellar(tipo, parametro, filas):
    """SHA-256 del contenido canónico del reporte.

    Canónico significa: JSON con claves ordenadas y sin espacios. Dos
    generaciones del mismo reporte sobre los mismos datos dan el mismo
    sello; si un byte cambia, el sello cambia. Eso es lo que permite
    confrontar el archivo que recibió un auditor contra el registro.
    """
    canonico = json.dumps({"tipo": tipo, "parametro": parametro, "filas": filas},
                          sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def _limpiar(doc):
    doc = dict(doc)
    doc.pop("_id", None)
    for k, v in list(doc.items()):
        if isinstance(v, dt.datetime):
            doc[k] = v.isoformat()
    return doc


def _definicion(tipo):
    definicion = CATALOGO.get((tipo or "").strip().upper())
    if not definicion:
        raise ErrorApi("TIPO_DESCONOCIDO",
                       f"Tipo de reporte no reconocido. Validos: "
                       f"{', '.join(sorted(CATALOGO))}.", 404)
    return definicion


# --------------------------------------------------------------- catálogo
@app.get(f"{BASE}/catalogo")
@requiere_permiso(*sorted({p for d in CATALOGO.values() for p in d["permisos"]}))
def catalogo():
    """Qué reportes existen, qué exige cada uno y qué significan sus columnas.

    Se filtra por los permisos de quien pregunta: un colaborador no debe ver
    ni el nombre del reporte de bitácora.
    """
    mios = set(getattr(g, "permisos", set()) or set())
    elementos = [
        {"tipo": tipo,
         "titulo": d["titulo"],
         "nota": d["nota"],
         "parametro": d["parametro"],
         "parametro_obligatorio": bool(d.get("parametro_obligatorio")),
         "permisos": list(d["permisos"]),
         "formatos": list(FORMATOS)}
        for tipo, d in sorted(CATALOGO.items())
        if mios & set(d["permisos"])
    ]
    return responder({"elementos": elementos, "total": len(elementos)},
                     200, raiz="catalogo_reportes_respuesta")


# ------------------------------------------------------------- generación
@app.post(BASE)
@requiere_permiso(*sorted({p for d in CATALOGO.values() for p in d["permisos"]}))
def generar():
    """Genera un reporte, lo sella y lo guarda.

    El permiso se verifica DOS veces: el decorador comprueba que quien pide
    tenga alguno de los permisos de reportes, y aquí abajo se comprueba que
    tenga el del tipo concreto. Sin la segunda, cualquiera que pudiera
    generar el reporte de participación podría generar el de bitácora.
    """
    limite_consumo(maximo=30)
    cuerpo = cuerpo_peticion()
    tipo = (cuerpo.get("tipo") or "").strip().upper()
    definicion = _definicion(tipo)

    mios = set(getattr(g, "permisos", set()) or set())
    if not mios & set(definicion["permisos"]):
        _bitacora("REPORTE_GENERADO", "RECHAZADO_PERMISO", tipo)
        raise ErrorApi("PERMISO_INSUFICIENTE",
                       f"Este reporte exige uno de: "
                       f"{', '.join(definicion['permisos'])}.", 403)

    parametro = cuerpo.get("parametro")
    if isinstance(parametro, str):
        parametro = parametro.strip() or None
    if definicion.get("parametro_obligatorio") and not parametro:
        raise ErrorApi("VALIDACION", "Faltan campos obligatorios.", 422,
                       [{"campo": "parametro",
                         "problema": f"este reporte exige "
                                     f"'{definicion['parametro']}'"}])
    if parametro and not definicion["parametro"]:
        raise ErrorApi("PARAMETRO_INVALIDO",
                       f"El reporte {tipo} no admite parametro.", 400)

    constructor = definicion.get("params")
    params = constructor(parametro) if constructor else (
        (parametro,) if definicion["parametro"] else None)

    filas = [{k: _normalizar(v) for k, v in f.items()}
             for f in consultar(definicion["sql"], params)]

    if not filas:
        raise ErrorApi("SIN_DATOS",
                       "La consulta no devolvio filas. Revisa el parametro: un "
                       "reporte vacio se confunde con un reporte sin supresiones.",
                       404)

    columnas = list(filas[0].keys())
    # La base no usa un estado llamado 'SUPRIMIDO': distingue el motivo
    # (GRUPO_INSUFICIENTE, PRESUPUESTO_PRIVACIDAD_AGOTADO). Suprimido es todo
    # lo que no llego a PUBLICADO, y se cuenta para poder decir en el propio
    # reporte cuantas filas van sin valor y por que.
    def _es_suprimida(f):
        estado = str(f.get("estado_publicacion") or f.get("motivo_supresion") or "")
        return bool(estado) and estado.upper() != "PUBLICADO"

    suprimidas = sum(1 for f in filas if _es_suprimida(f))

    documento = {
        "reporte_id": f"RPT-{uuid.uuid4().hex[:12].upper()}",
        "tipo": tipo,
        "titulo": definicion["titulo"],
        "nota": definicion["nota"],
        "parametro": parametro,
        "columnas": columnas,
        "filas": filas,
        "total_filas": len(filas),
        "filas_suprimidas": suprimidas,
        "sello_sha256": _sellar(tipo, parametro, filas),
        "generado_por": (g.get("actor") or {}).get("sub"),
        "perfil_generador": (g.get("actor") or {}).get("perfil"),
        "fecha_generacion": dt.datetime.now(dt.timezone.utc),
        "correlacion_id": getattr(g, "correlacion_id", ""),
        "epsilon_consumido": 0.0,
    }

    # El reporte puede traer el identificador de un ACTOR (quien operó el
    # sistema), pero nunca el de un EMPLEADO encuestado. Esta verificación
    # recorre el documento completo antes de que toque Mongo.
    verificar_sin_identidad({k: v for k, v in documento.items()
                             if k not in ("generado_por", "filas")})
    for fila in filas:
        verificar_sin_identidad({k: v for k, v in fila.items()
                                 if k != "actor_usuario_id"})

    base()["reportes"].insert_one(dict(documento))
    _bitacora("REPORTE_GENERADO", "EXITO", documento["reporte_id"])

    salida = _limpiar(documento)
    salida.pop("filas", None)          # el contenido se descarga aparte
    return responder(salida, 201, raiz="reporte_respuesta")


# --------------------------------------------------------------- consulta
@app.get(BASE)
@requiere_permiso(*sorted({p for d in CATALOGO.values() for p in d["permisos"]}))
def listar():
    """Reportes generados, del más reciente al más viejo."""
    limite_consumo(maximo=120)
    p, t = pagina()
    filtro = {}
    if request.args.get("tipo"):
        filtro["tipo"] = request.args["tipo"].strip().upper()
    if request.args.get("mios") in ("1", "true", "si"):
        filtro["generado_por"] = (g.get("actor") or {}).get("sub")

    # Solo se listan los tipos que quien pregunta podría generar.
    mios = set(getattr(g, "permisos", set()) or set())
    permitidos = [tipo for tipo, d in CATALOGO.items() if mios & set(d["permisos"])]
    if "tipo" in filtro and filtro["tipo"] not in permitidos:
        raise ErrorApi("PERMISO_INSUFICIENTE",
                       "No tienes permiso sobre ese tipo de reporte.", 403)
    filtro.setdefault("tipo", {"$in": permitidos})

    coleccion = base()["reportes"]
    total = coleccion.count_documents(filtro)
    cursor_mongo = (coleccion.find(filtro, {"filas": 0})
                    .sort("fecha_generacion", DESCENDING)
                    .skip((p - 1) * t).limit(t))
    return responder(sobre_pagina([_limpiar(d) for d in cursor_mongo],
                                  total, p, t),
                     200, raiz="reportes_respuesta")


@app.get(f"{BASE}/<reporte_id>")
@requiere_permiso(*sorted({p for d in CATALOGO.values() for p in d["permisos"]}))
def detalle(reporte_id):
    doc = base()["reportes"].find_one({"reporte_id": reporte_id}, {"filas": 0})
    if not doc:
        raise ErrorApi("NO_ENCONTRADO", "No existe ese reporte.", 404)
    mios = set(getattr(g, "permisos", set()) or set())
    if not mios & set(_definicion(doc["tipo"])["permisos"]):
        raise ErrorApi("PERMISO_INSUFICIENTE",
                       "No tienes permiso sobre ese tipo de reporte.", 403)
    return responder(_limpiar(doc), 200, raiz="reporte_respuesta")


@app.get(f"{BASE}/<reporte_id>/contenido")
@requiere_permiso(*sorted({p for d in CATALOGO.values() for p in d["permisos"]}))
def contenido(reporte_id):
    """Descarga el reporte en JSON, CSV o XML.

    Los tres salen del MISMO documento guardado, no de una consulta nueva.
    Si se volviera a consultar la base, el CSV y el JSON del mismo reporte
    podrían diferir y el sello no cuadraría con ninguno de los dos.
    """
    limite_consumo(maximo=60)
    formato = (request.args.get("formato") or "json").strip().lower()
    if formato not in FORMATOS:
        raise ErrorApi("PARAMETRO_INVALIDO",
                       f"Formato no soportado. Validos: {', '.join(FORMATOS)}.",
                       400)

    doc = base()["reportes"].find_one({"reporte_id": reporte_id})
    if not doc:
        raise ErrorApi("NO_ENCONTRADO", "No existe ese reporte.", 404)
    mios = set(getattr(g, "permisos", set()) or set())
    if not mios & set(_definicion(doc["tipo"])["permisos"]):
        _bitacora("REPORTE_DESCARGADO", "RECHAZADO_PERMISO", reporte_id)
        raise ErrorApi("PERMISO_INSUFICIENTE",
                       "No tienes permiso sobre ese tipo de reporte.", 403)

    _bitacora("REPORTE_DESCARGADO", "EXITO", reporte_id)
    filas = doc.get("filas") or []
    columnas = doc.get("columnas") or (list(filas[0].keys()) if filas else [])
    nombre = f"{doc['reporte_id']}_{doc['tipo'].lower()}"

    if formato == "csv":
        buffer = io.StringIO()
        # QUOTE_ALL a propósito: la explicación de una regla trae comas, y
        # una sola coma sin comillas corre todas las columnas siguientes.
        escritor = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        escritor.writerow(columnas)
        for fila in filas:
            escritor.writerow(["" if fila.get(c) is None else fila.get(c)
                               for c in columnas])
        # BOM para que Excel en Windows abra los acentos bien sin pedir nada.
        cuerpo = "﻿" + buffer.getvalue()
        return Response(
            cuerpo, 200,
            {"Content-Type": "text/csv; charset=utf-8",
             "Content-Disposition": f'attachment; filename="{nombre}.csv"',
             "X-Reporte-Sello": doc["sello_sha256"],
             "X-Reporte-Filas-Suprimidas": str(doc.get("filas_suprimidas", 0))})

    if formato == "xlsx":
        return Response(
            _formatos.a_excel(doc, filas, columnas), 200,
            {"Content-Type": "application/vnd.openxmlformats-officedocument"
                             ".spreadsheetml.sheet",
             "Content-Disposition": f'attachment; filename="{nombre}.xlsx"',
             "X-Reporte-Sello": doc["sello_sha256"],
             "X-Reporte-Filas-Suprimidas": str(doc.get("filas_suprimidas", 0))})

    if formato == "pdf":
        return Response(
            _formatos.a_pdf(doc, filas, columnas), 200,
            {"Content-Type": "application/pdf",
             "Content-Disposition": f'attachment; filename="{nombre}.pdf"',
             "X-Reporte-Sello": doc["sello_sha256"],
             "X-Reporte-Filas-Suprimidas": str(doc.get("filas_suprimidas", 0))})

    if formato == "xml":
        xml = a_xml({"reporte_id": doc["reporte_id"], "tipo": doc["tipo"],
                     "titulo": doc["titulo"], "parametro": doc.get("parametro"),
                     "sello_sha256": doc["sello_sha256"],
                     "total_filas": doc.get("total_filas", len(filas)),
                     "filas_suprimidas": doc.get("filas_suprimidas", 0),
                     "filas": filas}, raiz="reporte")
        return Response(
            xml, 200,
            {"Content-Type": "application/xml; charset=utf-8",
             "Content-Disposition": f'attachment; filename="{nombre}.xml"',
             "X-Reporte-Sello": doc["sello_sha256"]})

    return Response(
        json.dumps(_limpiar(doc), ensure_ascii=False, indent=2),
        200,
        {"Content-Type": "application/json; charset=utf-8",
         "Content-Disposition": f'attachment; filename="{nombre}.json"',
         "X-Reporte-Sello": doc["sello_sha256"]})


@app.get(f"{BASE}/<reporte_id>/grafica")
@requiere_token
def grafica(reporte_id):
    """Configuración de Highcharts para este reporte.

    Devuelve la CONFIGURACIÓN, no una imagen. El portal ya sirve
    Highcharts localmente y es quien tiene la pantalla; un microservicio
    que generara imágenes necesitaría un navegador sin interfaz dentro del
    contenedor —decenas de megabytes y una superficie de ataque nueva—
    para producir algo que el navegador del usuario dibuja gratis.

    Las filas suprimidas NO entran en la serie y su conteo viaja en el
    subtítulo. Meterlas como ceros movería la gráfica hacia abajo y haría
    ver un problema donde lo que hay es ausencia de dato.
    """
    limite_consumo(maximo=120)
    doc = base()["reportes"].find_one({"reporte_id": reporte_id})
    if not doc:
        raise ErrorApi("NO_ENCONTRADO", "No existe ese reporte.", 404)
    mios = set(getattr(g, "permisos", set()) or set())
    if not mios & set(_definicion(doc["tipo"])["permisos"]):
        raise ErrorApi("PERMISO_INSUFICIENTE",
                       "No tienes permiso sobre ese tipo de reporte.", 403)

    filas = doc.get("filas") or []
    columnas = doc.get("columnas") or (list(filas[0].keys()) if filas else [])
    salida = _formatos.a_highcharts(doc, filas, columnas)
    salida["reporte_id"] = reporte_id
    return responder(salida, 200, raiz="grafica_respuesta")


@app.post(f"{BASE}/comparativo")
@requiere_permiso("AGREGADO_UNIDAD", "AGREGADO_GLOBAL")
def comparativo():
    """Compara DOS reportes ya generados del mismo tipo.

    Es el «reporte comparativo» que pide la especificación, y la decisión
    que lo hace honesto es de dónde salen los datos: de dos reportes YA
    GENERADOS, con sus dos sellos, no de dos consultas nuevas. Así el
    comparativo se puede auditar —se sabe exactamente qué dos fotos se
    restaron— y no consume presupuesto de épsilon, porque ninguno de los
    dos vuelve a calcular nada.

    POR QUÉ NO SE COMPARA LO SUPRIMIDO
    ----------------------------------
    Si una unidad está publicada en una campaña y suprimida en la otra, la
    diferencia no existe: no es cero ni «mejoró». Esas filas se devuelven
    aparte, en `sin_comparacion`, con el motivo. Restarlas contra cero
    produciría un número que parece un hallazgo y es un artefacto.

    POR QUÉ LA DIFERENCIA LLEVA UNA ADVERTENCIA
    -------------------------------------------
    Los dos valores traen ruido de Laplace. Una diferencia más chica que
    el ruido no significa nada: puede ser enteramente azar. Cada fila dice
    si la diferencia supera la escala del ruido de los dos puntos, que es
    la única forma de que alguien no lea una variación de 0.1 como una
    mejora.
    """
    limite_consumo(maximo=30)
    cuerpo = cuerpo_peticion()
    id_a = (cuerpo.get("reporte_base") or "").strip()
    id_b = (cuerpo.get("reporte_comparado") or "").strip()
    if not id_a or not id_b:
        raise ErrorApi("CAMPOS_OBLIGATORIOS",
                       "Faltan 'reporte_base' y 'reporte_comparado'.", 400,
                       [{"campo": "reporte_base", "problema": "requerido"},
                        {"campo": "reporte_comparado", "problema": "requerido"}])
    if id_a == id_b:
        raise ErrorApi("PARAMETRO_INVALIDO",
                       "Los dos reportes son el mismo.", 400)

    coleccion = base()["reportes"]
    doc_a = coleccion.find_one({"reporte_id": id_a})
    doc_b = coleccion.find_one({"reporte_id": id_b})
    for identificador, doc in ((id_a, doc_a), (id_b, doc_b)):
        if not doc:
            raise ErrorApi("NO_ENCONTRADO",
                           f"No existe el reporte {identificador}.", 404)
    if doc_a["tipo"] != doc_b["tipo"]:
        raise ErrorApi("TIPOS_DISTINTOS",
                       f"No se pueden comparar un {doc_a['tipo']} con un "
                       f"{doc_b['tipo']}: tienen columnas distintas y la "
                       f"resta no significaria nada.", 422)

    mios = set(getattr(g, "permisos", set()) or set())
    if not mios & set(_definicion(doc_a["tipo"])["permisos"]):
        raise ErrorApi("PERMISO_INSUFICIENTE",
                       "No tienes permiso sobre ese tipo de reporte.", 403)

    columnas = doc_a.get("columnas") or []
    clave = [c for c in ("unidad_organizacional_id", "dimension",
                         "unidad", "dimension_id") if c in columnas]
    valor = next((c for c in ("valor_protegido", "cobertura_porcentaje",
                              "total") if c in columnas), None)
    if not clave or not valor:
        raise ErrorApi("NO_COMPARABLE",
                       f"El tipo {doc_a['tipo']} no tiene una llave de "
                       f"agrupacion y una columna numerica que permitan "
                       f"comparar.", 422)

    def indexar(doc):
        return {tuple(str(f.get(c)) for c in clave): f
                for f in (doc.get("filas") or [])}

    filas_a, filas_b = indexar(doc_a), indexar(doc_b)
    comparadas, sin_comparacion = [], []

    for llave in sorted(set(filas_a) | set(filas_b)):
        fila_a, fila_b = filas_a.get(llave), filas_b.get(llave)
        etiqueta = dict(zip(clave, llave))

        if fila_a is None or fila_b is None:
            sin_comparacion.append({**etiqueta, "motivo":
                "la unidad aparece en un reporte y no en el otro"})
            continue
        va, vb = fila_a.get(valor), fila_b.get(valor)
        if va is None or vb is None:
            sin_comparacion.append({**etiqueta, "motivo":
                "suprimida en al menos uno de los dos: la diferencia no "
                "existe, no es cero"})
            continue

        diferencia = round(float(vb) - float(va), 3)
        # La escala del ruido de los dos puntos. Si la diferencia no la
        # supera, puede ser enteramente azar.
        ruido = max(float(fila_a.get("escala_ruido") or 0),
                    float(fila_b.get("escala_ruido") or 0))
        comparadas.append({
            **etiqueta,
            "valor_base": float(va),
            "valor_comparado": float(vb),
            "diferencia": diferencia,
            "supera_el_ruido": bool(ruido) and abs(diferencia) > ruido,
            "lectura": _lectura_comparativa(diferencia, ruido),
        })

    return responder({
        "reporte_base": {"reporte_id": id_a, "parametro": doc_a.get("parametro"),
                         "sello_sha256": doc_a.get("sello_sha256")},
        "reporte_comparado": {"reporte_id": id_b, "parametro": doc_b.get("parametro"),
                              "sello_sha256": doc_b.get("sello_sha256")},
        "tipo": doc_a["tipo"],
        "columna_comparada": valor,
        "comparadas": comparadas,
        "total_comparadas": len(comparadas),
        "sin_comparacion": sin_comparacion,
        "total_sin_comparacion": len(sin_comparacion),
        # Cero, y obligatorio: comparar dos reportes ya generados no vuelve
        # a calcular nada sobre los datos crudos.
        "epsilon_consumido": 0.0,
        "nota": "La diferencia se calcula entre dos valores que YA traen "
                "ruido. Una diferencia que no supera la escala del ruido "
                "puede ser enteramente azar y no describe un cambio real.",
    }, 200, raiz="comparativo_respuesta")


def _lectura_comparativa(diferencia, ruido):
    if ruido and abs(diferencia) <= ruido:
        return ("Dentro del ruido: no se puede afirmar que haya cambiado "
                "nada.")
    if diferencia > 0:
        return "Subio por encima del ruido."
    if diferencia < 0:
        return "Bajo por debajo del ruido."
    return "Sin cambio."


@app.post(f"{BASE}/<reporte_id>/verificar")
@requiere_permiso("BITACORA_CONSULTAR", "PARAMETRO_ADMIN")
def verificar(reporte_id):
    """Confronta un sello contra el reporte guardado.

    Es la operación que cierra el círculo: a un auditor le llegó un archivo
    por correo y quiere saber si es el que salió de aquí. Manda el sello y
    el servicio responde si coincide, sin necesidad de volver a mandar el
    archivo completo.
    """
    doc = base()["reportes"].find_one({"reporte_id": reporte_id})
    if not doc:
        raise ErrorApi("NO_ENCONTRADO", "No existe ese reporte.", 404)
    recibido = ((cuerpo_peticion()).get("sello_sha256") or "").strip()
    if not recibido:
        raise ErrorApi("VALIDACION", "Faltan campos obligatorios.", 422,
                       [{"campo": "sello_sha256", "problema": "es obligatorio"}])

    recalculado = _sellar(doc["tipo"], doc.get("parametro"), doc.get("filas") or [])
    coincide = (recibido.lower() == doc["sello_sha256"].lower())
    integro = (recalculado == doc["sello_sha256"])
    _bitacora("REPORTE_VERIFICADO", "EXITO" if coincide else "RECHAZADO", reporte_id)

    return responder(
        {"reporte_id": reporte_id,
         "coincide": coincide,
         "integro": integro,
         "sello_registrado": doc["sello_sha256"],
         "mensaje": ("El sello coincide: el archivo es el que genero este "
                     "servicio." if coincide else
                     "El sello NO coincide: el archivo fue modificado o "
                     "proviene de otra generacion.")},
        200, raiz="verificacion_respuesta")


@app.post(f"{BASE}/indices")
@requiere_permiso("PARAMETRO_ADMIN")
def crear_indices():
    creados = asegurar_indices(INDICES)
    return responder({"indices": creados, "total": len(creados)},
                     200, raiz="indices_respuesta")
