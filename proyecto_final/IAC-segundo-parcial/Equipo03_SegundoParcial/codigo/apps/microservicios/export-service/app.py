"""
export-service — egreso e ingreso controlado de agregados.

QUÉ HACE QUE reports-service NO HAGA
-------------------------------------
reports-service exporta UN REPORTE: una forma fija, que alguien revisó una
vez, con su propio sello. Este servicio exporta una SELECCIÓN LIBRE —las
unidades, las campañas y las dimensiones que quien exporta elija— y esa
diferencia no es de tamaño, es de riesgo.

El archivo, fuera de aquí, no tiene control ninguno. Quien lo recibe puede
sumar y restar sin pedirle nada al sistema:

    Un archivo con «Operaciones» (120 personas) y con tres de sus cuatro
    hijas contiene la cuarta por resta, aunque esa cuarta nunca se haya
    publicado y aunque las cuatro consultas, pedidas una a una en la
    pantalla, se hubieran bloqueado.

Ese es el ataque por diferencia hecho sobre el archivo, y es el motivo por
el que el control del CONJUNTO va antes de escribir un solo byte. La
pantalla ya tiene su control, por sesión, en `comun.inferencia`; aquí se
usa el mismo cálculo del residuo a propósito, porque si el archivo usara
otro criterio, lo que la pantalla niega el archivo lo entregaría.

LAS CUATRO DECISIONES DEL SERVICIO
-----------------------------------
1. **Generar y descargar son dos actos, con dos permisos y dos registros.**
   Un archivo generado y nunca descargado deja rastro igual: es el intento
   lo que interesa ver. Y una tercera descarga del mismo archivo, una
   semana después, es una salida de datos distinta de la primera.

2. **Las filas suprimidas se exportan, sin valor y con su motivo.** Un
   archivo que las omitiera haría leer «8 unidades» donde hubo 12. El
   conteo va aparte en el registro, por lo mismo.

3. **Lo importado no se mezcla con lo calculado.** Un agregado que entra
   de fuera no pasó por el umbral k ni por el ruido: su número puede venir
   de donde sea. Va a `exportacion.agregado_externo`, otra tabla, con su
   procedencia. La separación es física y no una columna de bandera que
   una consulta puede olvidar filtrar.

4. **No se consume presupuesto de épsilon.** Se lee
   `agregado.v_tablero_unidad`, que son resultados YA publicados. Si
   exportar llamara a la función de cálculo, bastarían unas cuantas
   exportaciones para agotar el presupuesto de la campaña y dejarla sin
   poder publicar nada.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import uuid

from flask import Response, g, request

from comun import (ErrorApi, VERSION_API, crear_servicio, cuerpo_peticion,
                   formatos as _formatos, k_minimo, limite_consumo,
                   obtener_redis, pagina, responder, requiere_permiso,
                   sobre_pagina, verificar_conjunto)
from comun.datos import consultar, consultar_uno, cursor, ping as ping_pg
from comun.xmlizar import a_xml

os.environ.setdefault("NOMBRE_SERVICIO", "export-service")

FORMATOS_EXPORTACION = ("json", "xml", "csv", "pdf")
# La importación no admite PDF, y no es un olvido: un PDF es un formato de
# presentación. Extraer números de uno es adivinar dónde empieza cada
# celda, y un dato de bienestar leído con heurísticas es peor que no tener
# el dato.
FORMATOS_IMPORTACION = ("json", "xml", "csv")

# Tope de filas por archivo. No es una cortesía al servidor: un archivo de
# cien mil filas de agregados ya no lo revisa nadie antes de mandarlo, y
# una exportación que nadie revisa es una fuga esperando ocurrir.
MAXIMO_FILAS = 5000

COLUMNAS = ("unidad_organizacional_id", "unidad", "campania_id", "dimension",
            "estado_publicacion", "valor_protegido", "epsilon_aplicado",
            "mecanismo", "precision_advertencia")

# Las columnas que un archivo de importación tiene que traer. `valor` puede
# venir nulo —una fila suprimida en origen—, el resto no.
COLUMNAS_IMPORTACION = ("unidad_organizacional_id", "campania_id",
                        "dimension", "valor")


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "export-service",
    "Egreso e ingreso controlado de agregados, con control de fuga por "
    "conjuntos pequenos",
    comprobaciones={"postgresql": ping_pg, "redis": _ping_redis})

from contrato import montar as _montar_contrato  # noqa: E402
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/exportaciones"
BASE_IMP = f"/api/{VERSION_API}/importaciones"


# =========================================================================
# Apoyos
# =========================================================================

def _bitacora(accion, resultado, recurso=None):
    """Registra en la bitácora sin tumbar la operación principal.

    Los códigos usados aquí están declarados en la migración 009. Si
    faltara uno, la llave foránea haría fallar la inserción y este try se
    lo tragaría: es el defecto que la migración 007 vino a corregir, y por
    eso hay una prueba que compara los códigos del código contra los de la
    base.
    """
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO auditoria.bitacora (actor_usuario_id, actor_perfil, "
                " accion, tipo_recurso, recurso_id, resultado, correlacion_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                ((g.get("actor") or {}).get("sub"),
                 ((g.get("actor") or {}).get("perfil") or "ANONIMO")[:30],
                 accion, "EXPORTACION", str(recurso) if recurso else None,
                 resultado, getattr(g, "correlacion_id", "")))
    except Exception:
        app.logger.error("No se pudo escribir en la bitacora: %s", accion)


def _actor_id():
    return (g.get("actor") or {}).get("sub")


def _alcance_permite(unidad_id):
    """El alcance sale del perfil asignado, nunca del parámetro.

    Si saliera del parámetro, bastaría pedir otra unidad en el cuerpo para
    exportar los agregados de un área ajena.
    """
    actor = g.get("actor") or {}
    if actor.get("unidad_alcance") in (None, ""):
        return True
    return bool(consultar_uno(
        "WITH RECURSIVE arbol AS ("
        "  SELECT unidad_organizacional_id FROM organizacion.unidad_organizacional"
        "   WHERE unidad_organizacional_id = %s"
        "  UNION ALL"
        "  SELECT h.unidad_organizacional_id"
        "    FROM organizacion.unidad_organizacional h"
        "    JOIN arbol a ON h.unidad_padre_id = a.unidad_organizacional_id)"
        " SELECT 1 AS x FROM arbol WHERE unidad_organizacional_id = %s",
        (actor["unidad_alcance"], unidad_id)))


def _lista(cuerpo, clave):
    """Lee una lista del cuerpo, tolerando que venga un solo valor.

    Un cliente XML manda un elemento suelto cuando hay uno solo, y un
    cliente descuidado manda una cadena donde el contrato pide un arreglo.
    Rechazar eso con 422 sería correcto y también inútil: la intención no
    tiene ambigüedad.
    """
    valor = cuerpo.get(clave)
    if valor in (None, "", []):
        return []
    if isinstance(valor, str):
        return [valor.strip()] if valor.strip() else []
    if isinstance(valor, dict):          # <unidades><unidad>..</unidad></unidades>
        valor = list(valor.values())[0] if valor else []
        if isinstance(valor, str):
            return [valor]
    return [str(v).strip() for v in valor if str(v).strip()]


def _vigencia_horas():
    fila = consultar_uno(
        "SELECT agregado.fn_parametro('exportacion_vigencia_horas') AS v")
    try:
        return int(float(fila["v"]))
    except (TypeError, ValueError, KeyError):
        # El parámetro existe desde la migración 009. Si falta, se usa un
        # valor conservador en lugar de dejar el archivo sin vencimiento:
        # un enlace que no vence es el estado peligroso.
        return 72


def _serializable(valor):
    if isinstance(valor, (dt.date, dt.datetime)):
        return valor.isoformat()
    if hasattr(valor, "quantize"):       # Decimal
        return float(valor)
    return valor


# =========================================================================
# Catálogo de formatos
# =========================================================================
@app.get(f"{BASE}/formatos")
@requiere_permiso("EXPORTACION_GENERAR", "EXPORTACION_DESCARGAR")
def formatos_disponibles():
    return responder({
        "exportacion": [
            {"formato": "json", "tipo_mime": "application/json",
             "validado_contra": "JSON Schema 2020-12 publicado en /esquema.json"},
            {"formato": "xml", "tipo_mime": "application/xml",
             "validado_contra": "XSD publicado en /esquema.xsd"},
            {"formato": "csv", "tipo_mime": "text/csv",
             "nota": "Un nulo se escribe «—» y nunca vacio: una celda vacia "
                     "se suma como cero en una hoja de calculo, y un "
                     "promedio con ceros de unidades suprimidas da un "
                     "numero mas bajo que el real."},
            {"formato": "pdf", "tipo_mime": "application/pdf",
             "nota": "Lleva impresa la advertencia de ruido: quien reciba "
                     "el archivo suelto, sin la pantalla, tiene que poder "
                     "saber que el valor no es el promedio real."},
        ],
        "importacion": list(FORMATOS_IMPORTACION),
        "por_que_no_se_importa_pdf":
            "Un PDF es un formato de presentacion. Extraer numeros de uno "
            "es adivinar donde empieza cada celda, y un dato de bienestar "
            "leido con heuristicas es peor que no tener el dato.",
        "maximo_filas": MAXIMO_FILAS,
        "epsilon_consumido_por_exportar": 0.0,
    }, 200, raiz="formatos_respuesta")


# =========================================================================
# Generar una exportación
# =========================================================================
@app.post(BASE)
@requiere_permiso("EXPORTACION_GENERAR")
def generar():
    """Arma el archivo. No lo entrega: descargarlo es otro acto."""
    limite_consumo(maximo=20)
    cuerpo = cuerpo_peticion()

    formato = (cuerpo.get("formato") or "").strip().lower()
    campanias = _lista(cuerpo, "campanias")
    unidades = _lista(cuerpo, "unidades")
    dimensiones = _lista(cuerpo, "dimensiones")

    problemas = []
    if formato not in FORMATOS_EXPORTACION:
        problemas.append({"campo": "formato",
                          "problema": f"uno de: "
                                      f"{', '.join(FORMATOS_EXPORTACION)}"})
    if not campanias:
        problemas.append({"campo": "campanias",
                          "problema": "al menos una. Sin campania la "
                                      "seleccion seria toda la historia"})
    if not unidades:
        problemas.append({"campo": "unidades", "problema": "al menos una"})
    if problemas:
        raise ErrorApi("VALIDACION", "La solicitud tiene campos invalidos.",
                       422, problemas)

    # --- existencia y alcance, antes de cualquier lectura de datos -----
    for campania in campanias:
        if not consultar_uno("SELECT 1 AS x FROM catalogo.campania "
                             " WHERE campania_id = %s", (campania,)):
            raise ErrorApi("CAMPANIA_NO_EXISTE",
                           f"La campania {campania} no existe.", 422)
    for unidad in unidades:
        if not consultar_uno(
                "SELECT 1 AS x FROM organizacion.unidad_organizacional "
                " WHERE unidad_organizacional_id = %s", (unidad,)):
            raise ErrorApi("UNIDAD_NO_EXISTE",
                           f"La unidad {unidad} no existe.", 422)
        if not _alcance_permite(unidad):
            _bitacora("EXPORTACION_BLOQUEADA", "RECHAZADO_PERMISO", unidad)
            raise ErrorApi("FUERA_DE_ALCANCE",
                           f"Tu perfil no tiene alcance sobre {unidad}.", 403)

    # --- el control que define al servicio ------------------------------
    # Va ANTES de leer y de escribir: si se hiciera después, el archivo ya
    # existiría en memoria y bastaría un error de programación más adelante
    # para que saliera igual.
    k = k_minimo(consultar_uno)
    try:
        verificar_conjunto(unidades, consultar_uno, k)
    except ErrorApi as error:
        _registrar_rechazo(formato, cuerpo, error)
        _bitacora("EXPORTACION_BLOQUEADA", "RECHAZADO")
        raise

    filas = _leer_agregados(campanias, unidades, dimensiones)
    if len(filas) > MAXIMO_FILAS:
        raise ErrorApi(
            "SELECCION_DEMASIADO_GRANDE",
            f"La seleccion da {len(filas)} filas y el tope es "
            f"{MAXIMO_FILAS}. No es un limite del servidor: un archivo de "
            f"ese tamano ya no lo revisa nadie antes de mandarlo, y una "
            f"exportacion que nadie revisa es una fuga esperando ocurrir. "
            f"Acota las campanias o las dimensiones.", 422,
            [{"campo": "filas", "problema": str(len(filas))},
             {"campo": "maximo", "problema": str(MAXIMO_FILAS)}])
    if not filas:
        raise ErrorApi("SIN_DATOS",
                       "La seleccion no devolvio ninguna fila. Revisa que "
                       "las campanias esten publicadas.", 404)

    publicadas = sum(1 for f in filas if f.get("valor_protegido") is not None)
    suprimidas = len(filas) - publicadas

    exportacion_id = f"EXP-{uuid.uuid4().hex[:16].upper()}"
    documento = _encabezado(exportacion_id, formato, campanias, unidades,
                            dimensiones, publicadas, suprimidas)
    contenido, tipo_mime = _construir(formato, documento, filas)
    sello = hashlib.sha256(contenido).hexdigest()

    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO exportacion.solicitud "
            " (exportacion_id, actor_usuario_id, formato, seleccion, "
            "  filas_publicadas, filas_suprimidas, sello_sha256, bytes, "
            "  contenido, estado, vence_en) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'GENERADA', "
            "        now() + make_interval(hours => %s))",
            (exportacion_id, _actor_id(), formato,
             json.dumps({"campanias": campanias, "unidades": unidades,
                         "dimensiones": dimensiones}),
             publicadas, suprimidas, sello, len(contenido),
             memoryview(contenido), _vigencia_horas()))

    _bitacora("EXPORTACION_GENERADA", "EXITO", exportacion_id)
    return responder({
        "exportacion_id": exportacion_id,
        "formato": formato,
        "sello_sha256": sello,
        "bytes": len(contenido),
        "filas_publicadas": publicadas,
        "filas_suprimidas": suprimidas,
        "vigencia_horas": _vigencia_horas(),
        "epsilon_consumido": 0.0,
        "descarga": f"{BASE}/{exportacion_id}/archivo",
        "nota": "El archivo esta armado pero NO entregado. Descargarlo "
                "exige EXPORTACION_DESCARGAR y queda registrado aparte: "
                "generar un archivo y llevarselo son dos actos distintos, "
                "y un archivo generado y nunca descargado tambien deja "
                "rastro.",
    }, 201, raiz="exportacion_creada")


def _registrar_rechazo(formato, cuerpo, error):
    """Una exportación negada también se registra.

    Si solo se registraran las que salen, el intento de llevarse un
    conjunto que permite aislar a tres personas no habría existido nunca, y
    es justo el intento lo que hay que poder ver.
    """
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO exportacion.solicitud "
                " (exportacion_id, actor_usuario_id, formato, seleccion, "
                "  estado, motivo_rechazo, vence_en) "
                "VALUES (%s,%s,%s,%s,'RECHAZADA',%s, now())",
                (f"EXP-{uuid.uuid4().hex[:16].upper()}", _actor_id(),
                 formato if formato in FORMATOS_EXPORTACION else "json",
                 json.dumps({"campanias": _lista(cuerpo, "campanias"),
                             "unidades": _lista(cuerpo, "unidades"),
                             "dimensiones": _lista(cuerpo, "dimensiones")}),
                 f"{error.codigo}: {error.mensaje}"[:1000]))
    except Exception:
        app.logger.error("No se pudo registrar la exportacion rechazada")


def _leer_agregados(campanias, unidades, dimensiones):
    """Lee de la vista de resultados YA PUBLICADOS.

    Nunca de `fn_calcular_agregado_protegido`: esa función consume
    presupuesto de épsilon, y bastarían unas cuantas exportaciones para
    agotar el de la campaña y dejarla sin poder publicar nada.

    Las filas suprimidas SE INCLUYEN, con `valor_protegido` nulo y su
    `estado_publicacion`. Omitirlas haría leer «8 unidades» donde hubo 12.
    """
    sql = ("SELECT unidad_organizacional_id, unidad, campania_id, dimension, "
           "       estado_publicacion, valor_protegido, epsilon_aplicado, "
           "       mecanismo, precision_advertencia "
           "  FROM agregado.v_tablero_unidad "
           " WHERE campania_id = ANY(%s) "
           "   AND unidad_organizacional_id = ANY(%s)")
    params = [list(campanias), list(unidades)]
    if dimensiones:
        sql += " AND dimension = ANY(%s)"
        params.append(list(dimensiones))
    sql += " ORDER BY campania_id, unidad_organizacional_id, dimension"
    return consultar(sql, tuple(params))


def _encabezado(exportacion_id, formato, campanias, unidades, dimensiones,
                publicadas, suprimidas):
    """Los metadatos que acompañan al archivo.

    `formatos.a_pdf` y `a_excel` esperan esta forma, la misma que usa
    reports-service. Mantenerla igual es lo que permite que los dos
    servicios compartan el generador en vez de tener una copia cada uno.
    """
    return {
        "reporte_id": exportacion_id,
        "tipo": "EXPORTACION_AGREGADOS",
        "titulo": "Exportacion de agregados protegidos",
        "fecha_generacion": _formatos.ahora_iso(),
        "generado_por": _actor_id(),
        "formato": formato,
        "parametros": {
            "campanias": campanias,
            "unidades": unidades,
            "dimensiones": dimensiones or ["(todas)"],
        },
        "filas_publicadas": publicadas,
        "filas_suprimidas": suprimidas,
        "epsilon_consumido": 0.0,
        "advertencia": _formatos.NOTA_RUIDO,
    }


def _construir(formato, documento, filas):
    """Arma los bytes del archivo en el formato pedido."""
    limpias = [{c: _serializable(f.get(c)) for c in COLUMNAS} for f in filas]

    if formato == "json":
        cuerpo = json.dumps({"exportacion": documento, "agregados": limpias},
                            ensure_ascii=False, indent=2)
        return cuerpo.encode("utf-8"), "application/json"

    if formato == "xml":
        # Envoltorio plural, hijo singular: la misma convención que el
        # resto del sistema, para que el mismo XSD y el mismo cliente de
        # escritorio sirvan aquí.
        cuerpo = a_xml({"exportacion": documento, "agregados": limpias},
                       raiz="ExportacionAgregados")
        return cuerpo.encode("utf-8"), "application/xml"

    if formato == "csv":
        buffer = io.StringIO()
        escritor = csv.writer(buffer, quoting=csv.QUOTE_ALL,
                              lineterminator="\r\n")
        # La advertencia va DENTRO del archivo. En una nota al pie de la
        # pantalla se pierde en cuanto alguien manda el CSV por correo.
        escritor.writerow([f"# {_formatos.NOTA_RUIDO}"])
        escritor.writerow([f"# exportacion: {documento['reporte_id']}",
                           f"publicadas: {documento['filas_publicadas']}",
                           f"suprimidas: {documento['filas_suprimidas']}"])
        escritor.writerow(list(COLUMNAS))
        for fila in limpias:
            # `_texto` convierte el nulo en «—» y nunca en vacío: una celda
            # vacía se suma como cero en una hoja de cálculo.
            escritor.writerow([_formatos._texto(fila[c]) for c in COLUMNAS])
        return buffer.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"

    if formato == "pdf":
        return (_formatos.a_pdf(documento, limpias, list(COLUMNAS)),
                "application/pdf")

    raise ErrorApi("FORMATO_NO_SOPORTADO",
                   f"Formato '{formato}' no soportado.", 422)


# =========================================================================
# Consultar y descargar
# =========================================================================
@app.get(BASE)
@requiere_permiso("EXPORTACION_GENERAR", "EXPORTACION_DESCARGAR",
                  "BITACORA_CONSULTAR")
def listar():
    """La bitácora de exportación.

    Quien tiene BITACORA_CONSULTAR ve todas; el resto, solo las propias.
    Que un especialista vea las exportaciones de otro no aporta a su
    trabajo y sí dice quién está mirando qué.
    """
    limite_consumo(maximo=60)
    p, t = pagina()
    todas = "BITACORA_CONSULTAR" in (g.get("permisos") or set())
    donde, params = ("1=1", []) if todas else ("actor_usuario_id = %s",
                                               [_actor_id()])
    total = (consultar_uno(f"SELECT count(*) AS n FROM exportacion.solicitud "
                           f" WHERE {donde}", tuple(params)) or {}).get("n", 0)
    filas = consultar(
        f"SELECT s.exportacion_id, s.actor_usuario_id, s.formato, s.seleccion, "
        f"       s.filas_publicadas, s.filas_suprimidas, s.sello_sha256, "
        f"       s.bytes, s.estado, s.motivo_rechazo, s.fecha_generacion, "
        f"       s.vence_en, "
        f"       (SELECT count(*) FROM exportacion.descarga d "
        f"         WHERE d.exportacion_id = s.exportacion_id) AS descargas "
        f"  FROM exportacion.solicitud s WHERE {donde} "
        f" ORDER BY s.fecha_generacion DESC LIMIT %s OFFSET %s",
        tuple(params) + (t, (p - 1) * t))
    datos = [{c: _serializable(v) for c, v in dict(f).items()} for f in filas]
    return responder(sobre_pagina(datos, total, p, t, clave="exportaciones"),
                     200, raiz="exportaciones_respuesta")


@app.get(f"{BASE}/<exportacion_id>")
@requiere_permiso("EXPORTACION_GENERAR", "EXPORTACION_DESCARGAR",
                  "BITACORA_CONSULTAR")
def detalle(exportacion_id):
    """Los metadatos y el historial de descargas. No el archivo."""
    limite_consumo(maximo=60)
    fila = _solicitud(exportacion_id)
    descargas = consultar(
        "SELECT descarga_id, actor_usuario_id, fecha_descarga "
        "  FROM exportacion.descarga WHERE exportacion_id = %s "
        " ORDER BY fecha_descarga DESC", (exportacion_id,))
    datos = {c: _serializable(v) for c, v in dict(fila).items()
             if c != "contenido"}
    datos["descargas"] = [{c: _serializable(v) for c, v in dict(d).items()}
                          for d in descargas]
    datos["vencida"] = _vencida(fila)
    return responder(datos, 200, raiz="exportacion_respuesta")


def _solicitud(exportacion_id):
    if not re.fullmatch(r"EXP-[0-9A-F]{16}", exportacion_id or ""):
        raise ErrorApi("PARAMETRO_INVALIDO",
                       "El identificador no tiene la forma EXP-<16 hex>.", 400)
    fila = consultar_uno("SELECT * FROM exportacion.solicitud "
                         " WHERE exportacion_id = %s", (exportacion_id,))
    if not fila:
        raise ErrorApi("NO_ENCONTRADO",
                       f"No existe la exportacion {exportacion_id}.", 404)
    # Quien no puede ver la bitácora completa solo ve lo propio.
    if ("BITACORA_CONSULTAR" not in (g.get("permisos") or set())
            and fila["actor_usuario_id"] != _actor_id()):
        raise ErrorApi("NO_ENCONTRADO",
                       f"No existe la exportacion {exportacion_id}.", 404)
    return fila


def _vencida(fila):
    vence = fila.get("vence_en")
    if not vence:
        return True
    ahora = dt.datetime.now(dt.timezone.utc)
    if vence.tzinfo is None:
        vence = vence.replace(tzinfo=dt.timezone.utc)
    return vence <= ahora


@app.get(f"{BASE}/<exportacion_id>/archivo")
@requiere_permiso("EXPORTACION_DESCARGAR")
def descargar(exportacion_id):
    """Entrega los bytes EXACTOS que se sellaron, y lo registra.

    No se regenera desde la selección. Si se regenerara, una campaña
    publicada entre la generación y la descarga daría un archivo distinto
    con el sello viejo, y el sello dejaría de servir para lo único que
    sirve: demostrar que el archivo que alguien recibió es el que se
    generó.
    """
    limite_consumo(maximo=40)
    fila = _solicitud(exportacion_id)

    if fila["estado"] == "RECHAZADA":
        raise ErrorApi("EXPORTACION_RECHAZADA",
                       f"Esa exportacion se nego y no tiene archivo. Motivo: "
                       f"{fila.get('motivo_rechazo')}", 409)
    if _vencida(fila):
        with cursor(commit=True) as cur:
            cur.execute("UPDATE exportacion.solicitud SET estado = 'VENCIDA' "
                        " WHERE exportacion_id = %s AND estado <> 'VENCIDA'",
                        (exportacion_id,))
        raise ErrorApi(
            "EXPORTACION_VENCIDA",
            f"El archivo vencio el {fila['vence_en'].isoformat()}. Hay que "
            f"volver a generarlo: un enlace de descarga que no vence sigue "
            f"sirviendo meses despues de que quien lo pidio dejo de "
            f"necesitarlo, o dejo la organizacion. El registro nuevo deja "
            f"ver que alguien volvio a pedir los mismos datos.", 410)

    contenido = bytes(fila["contenido"] or b"")
    if not contenido:
        raise ErrorApi("ALMACEN_NO_DISPONIBLE",
                       "El registro existe pero el archivo no. No se "
                       "reconstruye: el sello no cuadraria.", 503)

    # Se vuelve a calcular el sello sobre lo que se va a entregar. Si no
    # coincide, el archivo se alteró en la base y no se entrega: entregarlo
    # con el sello viejo sería afirmar una integridad que no hay.
    if hashlib.sha256(contenido).hexdigest() != (fila["sello_sha256"] or ""):
        _bitacora("EXPORTACION_DESCARGADA", "RECHAZADO", exportacion_id)
        raise ErrorApi("ARCHIVO_ALTERADO",
                       "El contenido no coincide con su sello. No se "
                       "entrega.", 409)

    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO exportacion.descarga "
            " (exportacion_id, actor_usuario_id, correlacion_id) "
            "VALUES (%s,%s,%s)",
            (exportacion_id, _actor_id(), getattr(g, "correlacion_id", "")))
        cur.execute("UPDATE exportacion.solicitud SET estado = 'DESCARGADA' "
                    " WHERE exportacion_id = %s", (exportacion_id,))

    _bitacora("EXPORTACION_DESCARGADA", "EXITO", exportacion_id)
    extension = fila["formato"]
    tipos = {"json": "application/json", "xml": "application/xml",
             "csv": "text/csv; charset=utf-8", "pdf": "application/pdf"}
    return Response(contenido, 200, {
        "Content-Type": tipos.get(extension, "application/octet-stream"),
        "Content-Disposition": f'attachment; filename="{exportacion_id}.{extension}"',
        "X-Exportacion-Sello": fila["sello_sha256"],
        "X-Exportacion-Suprimidas": str(fila["filas_suprimidas"]),
    })


# =========================================================================
# Importación
# =========================================================================
@app.post(f"{BASE_IMP}/validar")
@requiere_permiso("IMPORTACION_APLICAR", "EXPORTACION_GENERAR")
def validar_importacion():
    """Revisa un archivo contra el contrato. No aplica nada.

    Validar y aplicar están separados por lo mismo que generar y descargar:
    revisar un archivo es inofensivo, y dar de alta agregados que vienen de
    fuera cambia lo que el sistema afirma.

    Se informa fila por fila. Un «no se pudo importar» sin detalle obliga a
    adivinar, y quien sube el archivo no tiene cómo arreglarlo.
    """
    limite_consumo(maximo=20)
    cuerpo = cuerpo_peticion()
    formato = (cuerpo.get("formato") or "").strip().lower()
    procedencia = (cuerpo.get("procedencia") or "").strip()
    contenido = cuerpo.get("contenido") or ""

    problemas = []
    if formato not in FORMATOS_IMPORTACION:
        problemas.append({"campo": "formato",
                          "problema": f"uno de: "
                                      f"{', '.join(FORMATOS_IMPORTACION)}"})
    if len(procedencia) < 5:
        problemas.append({
            "campo": "procedencia",
            "problema": "obligatoria, al menos 5 caracteres. Un agregado "
                        "sin procedencia es un numero sin dueno: dentro de "
                        "seis meses nadie puede decir si salio de este "
                        "sistema o de una estimacion"})
    if not contenido:
        problemas.append({"campo": "contenido", "problema": "requerido"})
    if problemas:
        raise ErrorApi("VALIDACION", "La solicitud tiene campos invalidos.",
                       422, problemas)

    crudas = _parsear(formato, contenido)
    validas, rechazos = _validar_filas(crudas)

    importacion_id = f"IMP-{uuid.uuid4().hex[:16].upper()}"
    sello = hashlib.sha256(contenido.encode("utf-8")).hexdigest()
    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO exportacion.importacion "
            " (importacion_id, actor_usuario_id, formato, procedencia, "
            "  sello_sha256, filas_recibidas, filas_validas, "
            "  filas_rechazadas, detalle_rechazos, estado) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (importacion_id, _actor_id(), formato, procedencia, sello,
             len(crudas), len(validas), len(rechazos),
             json.dumps(rechazos, ensure_ascii=False),
             "VALIDADA" if validas else "RECHAZADA"))

    _bitacora("IMPORTACION_VALIDADA",
              "EXITO" if validas else "RECHAZADO", importacion_id)
    return responder({
        "importacion_id": importacion_id,
        "estado": "VALIDADA" if validas else "RECHAZADA",
        "sello_sha256": sello,
        "filas_recibidas": len(crudas),
        "filas_validas": len(validas),
        "filas_rechazadas": len(rechazos),
        "detalle_rechazos": rechazos,
        "nota": "Nada se dio de alta todavia. Aplicar exige "
                "IMPORTACION_APLICAR, y lo aplicado va a "
                "exportacion.agregado_externo, NUNCA a los agregados "
                "calculados: un agregado que viene de fuera no paso por el "
                "umbral k ni por el ruido, y mezclarlos haria imposible "
                "distinguir un valor protegido de uno escrito a mano.",
    }, 201, raiz="importacion_validada")


def _parsear(formato, texto):
    """Convierte el archivo en una lista de diccionarios.

    Un archivo mal formado se rechaza con 422 y diciendo dónde falla, no
    con un 500. El mensaje del analizador se incluye porque es lo único que
    permite arreglar el archivo.
    """
    try:
        if formato == "json":
            datos = json.loads(texto)
            if isinstance(datos, dict):
                # Se acepta tanto el archivo que este servicio produce
                # (con encabezado) como una lista suelta.
                datos = datos.get("agregados", datos.get("agregado", []))
            if not isinstance(datos, list):
                raise ValueError("se esperaba una lista de agregados")
            return datos

        if formato == "csv":
            # Las líneas de comentario que este servicio escribe al
            # exportar se saltan, para que un archivo exportado se pueda
            # volver a importar sin editarlo a mano.
            #
            # El `lstrip` quita también la marca de orden de bytes (BOM).
            # El CSV se escribe en utf-8-sig —lo necesita Excel para abrir
            # los acentos bien— y eso pone ﻿ al principio de la
            # PRIMERA línea, que es justo una de las de comentario. Sin
            # quitarlo, esa línea no se reconoce como comentario, pasa a
            # ser la cabecera, y entonces TODAS las filas salen con las
            # columnas equivocadas: el archivo se rechaza entero con
            # «faltan columnas» y el motivo no se parece en nada a la
            # causa.
            lineas = [l for l in texto.splitlines()
                      if l.strip() and not l.lstrip('﻿"\' ').startswith("#")]
            return list(csv.DictReader(io.StringIO("\n".join(lineas))))

        if formato == "xml":
            from lxml import etree
            raiz = etree.fromstring(texto.encode("utf-8"))
            filas = []
            for nodo in raiz.iter():
                hijos = {h.tag.split("}")[-1]: (h.text or "").strip()
                         for h in nodo}
                if "unidad_organizacional_id" in hijos:
                    filas.append(hijos)
            return filas
    except ErrorApi:
        raise
    except Exception as e:
        raise ErrorApi("ARCHIVO_MAL_FORMADO",
                       f"El archivo no se pudo leer como {formato}: "
                       f"{str(e)[:200]}", 422)

    raise ErrorApi("FORMATO_NO_SOPORTADO",
                   f"Formato '{formato}' no soportado para importar.", 422)


def _validar_filas(crudas):
    """Valida contra el contrato Y contra los catálogos de la base.

    Las dos cosas, y la segunda importa más: una fila puede tener todas sus
    columnas y referirse a una unidad que no existe. Darla de alta dejaría
    un agregado colgando de una unidad fantasma, que después aparece en un
    tablero sin que nadie sepa de dónde salió.
    """
    validas, rechazos = [], []
    for indice, cruda in enumerate(crudas, start=1):
        fila = {k: (v if v not in ("", "—", "-") else None)
                for k, v in dict(cruda).items()}
        faltan = [c for c in COLUMNAS_IMPORTACION if c not in fila]
        if faltan:
            rechazos.append({"fila": indice,
                             "problema": f"faltan columnas: "
                                         f"{', '.join(faltan)}"})
            continue

        unidad = (fila.get("unidad_organizacional_id") or "").strip()
        campania = (fila.get("campania_id") or "").strip()
        dimension = (fila.get("dimension") or "").strip()
        if not (unidad and campania and dimension):
            rechazos.append({"fila": indice,
                             "problema": "unidad, campania y dimension no "
                                         "pueden venir vacias"})
            continue

        if not consultar_uno("SELECT 1 AS x FROM organizacion.unidad_organizacional"
                             " WHERE unidad_organizacional_id = %s", (unidad,)):
            rechazos.append({"fila": indice,
                             "problema": f"la unidad {unidad} no existe en "
                                         f"este sistema"})
            continue
        if not consultar_uno("SELECT 1 AS x FROM catalogo.campania "
                             " WHERE campania_id = %s", (campania,)):
            rechazos.append({"fila": indice,
                             "problema": f"la campania {campania} no existe"})
            continue

        valor = fila.get("valor")
        if valor is not None:
            try:
                valor = float(valor)
            except (TypeError, ValueError):
                rechazos.append({"fila": indice,
                                 "problema": f"valor no numerico: {valor!r}"})
                continue
            # La escala del instrumento es 1..5. Un valor fuera de rango no
            # es un agregado de este sistema, venga de donde venga.
            if not 1.0 <= valor <= 5.0:
                rechazos.append({
                    "fila": indice,
                    "problema": f"valor {valor} fuera de la escala 1..5 del "
                                f"instrumento"})
                continue

        validas.append({"unidad_organizacional_id": unidad,
                        "campania_id": campania,
                        "dimension": dimension,
                        "valor": valor,
                        "epsilon_declarado": _numero(fila.get("epsilon_aplicado")),
                        "n_declarado": _entero(fila.get("n_observaciones"))})
    return validas, rechazos


def _numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _entero(valor):
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return None


@app.post(f"{BASE_IMP}/<importacion_id>/aplicar")
@requiere_permiso("IMPORTACION_APLICAR")
def aplicar_importacion(importacion_id):
    """Da de alta las filas válidas, en la tabla de agregados externos.

    El archivo se vuelve a mandar y se comprueba contra el sello guardado.
    Si no coincide, no se aplica: validar un archivo y aplicar otro sería
    el agujero más obvio posible en un proceso de dos pasos.
    """
    limite_consumo(maximo=20)
    cuerpo = cuerpo_peticion()
    contenido = cuerpo.get("contenido") or ""

    if not re.fullmatch(r"IMP-[0-9A-F]{16}", importacion_id or ""):
        raise ErrorApi("PARAMETRO_INVALIDO",
                       "El identificador no tiene la forma IMP-<16 hex>.", 400)
    fila = consultar_uno("SELECT * FROM exportacion.importacion "
                         " WHERE importacion_id = %s", (importacion_id,))
    if not fila:
        raise ErrorApi("NO_ENCONTRADO",
                       f"No existe la importacion {importacion_id}.", 404)
    if fila["estado"] == "APLICADA":
        raise ErrorApi("IMPORTACION_YA_APLICADA",
                       f"La importacion {importacion_id} ya se aplico.", 409)
    if fila["estado"] == "RECHAZADA":
        raise ErrorApi("IMPORTACION_RECHAZADA",
                       "Esa importacion no tiene filas validas que aplicar.",
                       409)
    if not contenido:
        raise ErrorApi("CAMPOS_OBLIGATORIOS",
                       "Falta 'contenido': hay que volver a mandar el mismo "
                       "archivo que se valido, para comprobarlo contra su "
                       "sello.", 400,
                       [{"campo": "contenido", "problema": "requerido"}])

    if hashlib.sha256(contenido.encode("utf-8")).hexdigest() != fila["sello_sha256"]:
        _bitacora("IMPORTACION_APLICADA", "RECHAZADO", importacion_id)
        raise ErrorApi("SELLO_NO_COINCIDE",
                       "El archivo no es el que se valido. Validar uno y "
                       "aplicar otro dejaria entrar cualquier cosa por la "
                       "puerta del segundo paso.", 409)

    validas, _ = _validar_filas(_parsear(fila["formato"], contenido))
    if not validas:
        raise ErrorApi("SIN_FILAS_VALIDAS",
                       "No quedan filas validas que aplicar.", 422)

    with cursor(commit=True) as cur:
        for v in validas:
            cur.execute(
                "INSERT INTO exportacion.agregado_externo "
                " (importacion_id, unidad_organizacional_id, campania_id, "
                "  dimension, valor, epsilon_declarado, n_declarado) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (importacion_id, unidad_organizacional_id, "
                "             campania_id, dimension) DO NOTHING",
                (importacion_id, v["unidad_organizacional_id"],
                 v["campania_id"], v["dimension"], v["valor"],
                 v["epsilon_declarado"], v["n_declarado"]))
        cur.execute("UPDATE exportacion.importacion SET estado = 'APLICADA' "
                    " WHERE importacion_id = %s", (importacion_id,))

    _bitacora("IMPORTACION_APLICADA", "EXITO", importacion_id)
    return responder({
        "importacion_id": importacion_id,
        "estado": "APLICADA",
        "filas_aplicadas": len(validas),
        "tabla": "exportacion.agregado_externo",
        "nota": "Estos valores NO pasaron por el umbral k ni por el ruido "
                "de Laplace de este sistema. Quedan en su propia tabla, con "
                "su procedencia, y no se unen con los agregados calculados "
                "en ninguna consulta que presente las dos cosas como el "
                "mismo tipo de dato.",
    }, 200, raiz="importacion_aplicada")


@app.get(f"{BASE_IMP}/<importacion_id>")
@requiere_permiso("IMPORTACION_APLICAR", "EXPORTACION_GENERAR",
                  "BITACORA_CONSULTAR")
def detalle_importacion(importacion_id):
    if not re.fullmatch(r"IMP-[0-9A-F]{16}", importacion_id or ""):
        raise ErrorApi("PARAMETRO_INVALIDO",
                       "El identificador no tiene la forma IMP-<16 hex>.", 400)
    fila = consultar_uno("SELECT * FROM exportacion.importacion "
                         " WHERE importacion_id = %s", (importacion_id,))
    if not fila:
        raise ErrorApi("NO_ENCONTRADO",
                       f"No existe la importacion {importacion_id}.", 404)
    datos = {c: _serializable(v) for c, v in dict(fila).items()}
    datos["agregados_externos"] = (consultar_uno(
        "SELECT count(*) AS n FROM exportacion.agregado_externo "
        " WHERE importacion_id = %s", (importacion_id,)) or {}).get("n", 0)
    return responder(datos, 200, raiz="importacion_respuesta")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PUERTO", "8121")))
