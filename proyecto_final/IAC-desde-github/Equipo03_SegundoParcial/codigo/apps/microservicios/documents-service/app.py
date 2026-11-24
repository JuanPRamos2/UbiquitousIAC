"""
documents-service — evidencias, avisos versionados y reportes.

Responsabilidad única: guardar y recuperar los documentos semiestructurados
del proyecto. Es el servicio que justifica MongoDB: un documento de
evidencia de consentimiento, un aviso de privacidad versionado y un reporte
organizacional tienen estructuras distintas entre sí y cambian de versión a
versión. Forzarlos a columnas fijas en PostgreSQL produciría o muchas
columnas nulas, o un modelo entidad-atributo-valor difícil de mantener.

Qué NO guarda: nada que identifique a una persona. Los documentos se
referencian por seudónimo o por unidad organizacional. La capa de acceso
rechaza el campo empleado_id aunque alguien lo mande por error.
"""
import datetime as dt
import hashlib
import os
import re
import uuid

from flask import g, request

from comun import (ErrorApi, VERSION_API, crear_servicio, cuerpo_peticion, limite_consumo,
                   obtener_redis, pagina, responder, requiere_permiso,
                   requiere_token, sobre_pagina)
from comun.datos import consultar_uno, cursor, ping as ping_pg
from comun.mongo import (ASCENDING, DESCENDING, asegurar_indices, base,
                         ping as ping_mongo, verificar_sin_identidad)

os.environ.setdefault("NOMBRE_SERVICIO", "documents-service")

MAX_EVIDENCIA_MB = 4
# base64 crece ~4/3 respecto a los bytes originales.
MAX_EVIDENCIA_BASE64 = int(MAX_EVIDENCIA_MB * 1024 * 1024 * 4 / 3)

TIPOS = {"EVIDENCIA_CONSENTIMIENTO", "AVISO_PRIVACIDAD", "REPORTE_ORGANIZACIONAL",
         "EVIDENCIA_ARCHIVO",
         "EVIDENCIA_APOYO"}

INDICES = {
    "documentos": [
        ([("documento_id", ASCENDING)], {"unique": True, "name": "ix_documento_id"}),
        ([("tipo", ASCENDING), ("fecha_creacion", DESCENDING)],
         {"name": "ix_tipo_fecha"}),
        ([("seudonimo_id", ASCENDING)], {"sparse": True, "name": "ix_seudonimo"}),
        ([("unidad_organizacional_id", ASCENDING), ("campania_id", ASCENDING)],
         {"sparse": True, "name": "ix_unidad_campania"}),
    ],
}


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "documents-service",
    "Almacena evidencias de consentimiento, avisos versionados y reportes",
    comprobaciones={"postgresql": ping_pg, "mongodb": ping_mongo,
                    "redis": _ping_redis})

import archivos
from contrato import montar as _montar_contrato
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/documentos"


def _bitacora(accion, resultado, recurso=None, tipo="DOCUMENTO"):
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO auditoria.bitacora (actor_usuario_id, actor_perfil, "
                " accion, tipo_recurso, recurso_id, resultado, correlacion_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                ((g.get("actor") or {}).get("sub"),
                 ((g.get("actor") or {}).get("perfil") or "ANONIMO")[:30],
                 accion, tipo, recurso, resultado, getattr(g, "correlacion_id", "")))
    except Exception:
        app.logger.error("No se pudo escribir en la bitacora: %s", accion)


def _limpiar(doc):
    """Quita el _id de Mongo, que no aporta nada al cliente, y normaliza fechas."""
    doc = dict(doc)
    doc.pop("_id", None)
    for k, v in list(doc.items()):
        if isinstance(v, dt.datetime):
            doc[k] = v.isoformat()
    return doc


@app.post(f"{BASE}/indices")
@requiere_permiso("PARAMETRO_ADMIN")
def crear_indices():
    """Declara los índices. Idempotente: se puede llamar en cada despliegue."""
    creados = asegurar_indices(INDICES)
    return responder({"indices": creados, "total": len(creados)},
                     200, raiz="indices_respuesta")


# ------------------------------------------------------------- inserción
@app.post(BASE)
@requiere_permiso("CONSENT_EVIDENCIA_AUDIT", "INSTRUMENTO_ADMIN", "PARAMETRO_ADMIN")
def crear():
    limite_consumo(maximo=60)
    cuerpo = cuerpo_peticion()

    problemas = []
    tipo = (cuerpo.get("tipo") or "").strip().upper()
    if tipo not in TIPOS:
        problemas.append({"campo": "tipo",
                          "problema": f"debe ser uno de: {', '.join(sorted(TIPOS))}"})
    contenido = cuerpo.get("contenido")
    if not isinstance(contenido, dict) or not contenido:
        problemas.append({"campo": "contenido",
                          "problema": "debe ser un objeto no vacio"})
    if problemas:
        raise ErrorApi("VALIDACION", "La solicitud tiene campos invalidos.",
                       422, problemas)

    # Aqui se hace cumplir la separacion de identidad, antes de tocar Mongo.
    verificar_sin_identidad(cuerpo)

    # Integridad referencial contra PostgreSQL: un documento que apunta a
    # una unidad inexistente es basura silenciosa.
    unidad = cuerpo.get("unidad_organizacional_id")
    if unidad and not consultar_uno(
            "SELECT 1 AS x FROM organizacion.unidad_organizacional "
            "WHERE unidad_organizacional_id = %s", (unidad,)):
        raise ErrorApi("UNIDAD_NO_EXISTE", f"La unidad {unidad} no existe.", 422)

    campania = cuerpo.get("campania_id")
    if campania and not consultar_uno(
            "SELECT 1 AS x FROM catalogo.campania WHERE campania_id = %s", (campania,)):
        raise ErrorApi("CAMPANIA_NO_EXISTE", f"La campania {campania} no existe.", 422)

    documento_id = f"DOC-{uuid.uuid4().hex[:12].upper()}"
    ahora = dt.datetime.now(dt.timezone.utc)
    import json as _json
    huella = hashlib.sha256(
        _json.dumps(contenido, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()

    doc = {
        "documento_id": documento_id,
        "tipo": tipo,
        "version": 1,
        "seudonimo_id": cuerpo.get("seudonimo_id"),
        "unidad_organizacional_id": unidad,
        "campania_id": campania,
        "contenido": contenido,
        "hash_contenido": huella,
        "etiquetas": cuerpo.get("etiquetas") or [],
        "creado_por": (g.actor or {}).get("sub"),
        "fecha_creacion": ahora,
        "fecha_actualizacion": ahora,
    }
    base()["documentos"].insert_one(doc)

    _bitacora("CATALOGO_MODIFICADO", "EXITO", recurso=documento_id)
    return responder({"documento_id": documento_id, "tipo": tipo, "version": 1,
                      "hash_contenido": huella,
                      "fecha_creacion": ahora.isoformat()},
                     201, raiz="documento_creado")


# ------------------------------------------- evidencia de una solicitud
@app.post(f"{BASE}/evidencia-apoyo")
@requiere_permiso("APOYO_SOLICITAR")
def adjuntar_evidencia_apoyo():
    """Adjunta una foto a la solicitud de apoyo de QUIEN LA LEVANTÓ.

    POR QUÉ ESTE ENDPOINT EXISTE Y NO SE USA EL GENERAL
    ---------------------------------------------------
    POST /documentos exige CONSENT_EVIDENCIA_AUDIT o INSTRUMENTO_ADMIN:
    permisos de administración que un colaborador no tiene ni debe tener.
    Pero el colaborador sí necesita poder adjuntar una foto a SU solicitud
    desde el teléfono, y esa es una operación distinta de «escribir
    cualquier documento en el repositorio».

    Las dos salidas fáciles eran malas. Darle al colaborador el permiso
    general lo habría dejado escribir documentos de cualquier tipo y leer
    el repositorio entero. Dejar la foto fuera habría obligado a describir
    de palabra lo que una foto muestra en un segundo.

    Así que la operación tiene su propio endpoint, con su propio permiso
    (el mismo que ya hace falta para pedir apoyo) y tres límites que el
    endpoint general no puede imponer:

      1. el tipo es siempre EVIDENCIA_APOYO: no se puede elegir;
      2. el seudónimo lo pone el SERVICIO leyéndolo de la participación de
         quien llama, no el cliente. Si lo pusiera el cliente, cualquiera
         podría adjuntar evidencia al caso de otra persona;
      3. no se acepta ningún campo de identidad, igual que en el resto.
    """
    limite_consumo(maximo=20)
    cuerpo = cuerpo_peticion()

    referencia = (cuerpo.get("referencia") or "").strip()
    contenido_base64 = cuerpo.get("contenido_base64") or ""
    problemas = []
    if not referencia:
        problemas.append({"campo": "referencia",
                          "problema": "el identificador de la solicitud es obligatorio"})
    if not contenido_base64:
        problemas.append({"campo": "contenido_base64",
                          "problema": "la imagen es obligatoria"})
    elif len(contenido_base64) > MAX_EVIDENCIA_BASE64:
        # El límite se revisa ANTES de decodificar: decodificar primero
        # significaría reservar en memoria la imagen que se va a rechazar.
        problemas.append({"campo": "contenido_base64",
                          "problema": f"la imagen pasa de {MAX_EVIDENCIA_MB} MB"})
    if problemas:
        raise ErrorApi("VALIDACION", "La solicitud tiene campos invalidos.",
                       422, problemas)

    actor = (g.actor or {}).get("sub")
    participacion = consultar_uno(
        "SELECT seudonimo_id FROM portal.v_participacion_propia "
        " WHERE usuario_id = %s", (actor,))
    if not participacion or not participacion.get("seudonimo_id"):
        raise ErrorApi("SIN_SEUDONIMO",
                       "La cuenta no tiene participacion operativa en el "
                       "programa, asi que no puede adjuntar evidencia.", 403)

    documento_id = f"DOC-{uuid.uuid4().hex[:12].upper()}"
    ahora = dt.datetime.now(dt.timezone.utc)
    contenido = {
        "solicitud_apoyo_id": referencia,
        "nombre_archivo": (cuerpo.get("nombre_archivo") or "evidencia.jpg")[:120],
        "tipo_mime": (cuerpo.get("tipo_mime") or "image/jpeg")[:60],
        "descripcion": (cuerpo.get("descripcion") or "")[:500],
        "contenido_base64": contenido_base64,
    }
    doc = {
        "documento_id": documento_id,
        "tipo": "EVIDENCIA_APOYO",
        "version": 1,
        # El seudonimo lo pone el servicio. Ver el punto 2 de arriba.
        "seudonimo_id": participacion["seudonimo_id"],
        "unidad_organizacional_id": None,
        "campania_id": None,
        "contenido": contenido,
        "hash_contenido": hashlib.sha256(contenido_base64.encode()).hexdigest(),
        "etiquetas": ["evidencia", "apoyo"],
        # `creado_por` NO se guarda aqui, a diferencia del endpoint general:
        # guardarlo pondria al lado el usuario_id y el seudonimo_id en el
        # mismo documento, que es exactamente la correspondencia que todo el
        # sistema evita.
        "fecha_creacion": ahora,
        "fecha_actualizacion": ahora,
    }
    verificar_sin_identidad(doc)
    base()["documentos"].insert_one(doc)

    # EVIDENCIA_CARGADA ya existe en auditoria.tipo_accion: inventar un
    # codigo nuevo haria fallar la insercion por llave foranea, en silencio.
    _bitacora("EVIDENCIA_CARGADA", "EXITO", recurso=documento_id)
    return responder({"documento_id": documento_id, "tipo": "EVIDENCIA_APOYO",
                      "solicitud_apoyo_id": referencia,
                      "hash_contenido": doc["hash_contenido"],
                      "fecha_creacion": ahora.isoformat()},
                     201, raiz="documento_creado")


# -------------------------------------------- archivos de evidencia
@app.post(f"{BASE}/archivos")
@requiere_permiso("INTERVENCION_SEGUIMIENTO", "INTERVENCION_APROBAR",
                  "CONSENT_EVIDENCIA_AUDIT")
def subir_archivo():
    """Carga un archivo de evidencia: lo valida, lo guarda y lo registra.

    Es la operación que antes solo existía dentro del portal web. Moverla
    aquí es lo que convierte la validación de formato y tamaño en una
    propiedad del sistema y no de una pantalla: ahora la aplicación de
    escritorio y la móvil también pueden adjuntar evidencia, y ningún
    cliente puede registrar un documento saltándose la comprobación.

    El archivo llega en base64 dentro del cuerpo JSON o XML. Se eligió eso
    sobre multipart porque los nueve servicios comparten un mismo lector de
    cuerpo —JSON y XML— y sus clientes ya saben hablarlo; agregar multipart
    solo aquí obligaría a cada cliente a tratar a este servicio distinto de
    los demás.

    El ORDEN de las operaciones no es casual:

      1. validar          (barato, y descarta lo que no debe entrar)
      2. comprobar el plan de intervención en PostgreSQL
      3. escribir el blob
      4. registrar los metadatos en MongoDB

    Si el paso 4 falla queda un blob huérfano, que no le hace daño a nadie
    y se puede recolectar después. Al revés —registrar primero y escribir
    después— quedaría un registro que apunta a un archivo inexistente, y
    eso sí es una evidencia rota que alguien va a tratar de abrir.
    """
    limite_consumo(maximo=30)
    cuerpo = cuerpo_peticion()

    import base64
    crudo = cuerpo.get("contenido_base64") or ""
    try:
        contenido = base64.b64decode(crudo, validate=True)
    except Exception:
        raise ErrorApi("BASE64_INVALIDO",
                       "El campo 'contenido_base64' no es base64 valido.", 400)

    extension, sello, nombre = archivos.validar(
        contenido, cuerpo.get("nombre_archivo"))

    intervencion = (cuerpo.get("intervencion_id") or "").strip()
    if not intervencion:
        raise ErrorApi("VALIDACION",
                       "La solicitud tiene campos invalidos.", 422,
                       [{"campo": "intervencion_id",
                         "problema": "un archivo sin plan al que pertenecer es "
                                     "basura que nadie podra interpretar despues"}])

    plan = consultar_uno(
        "SELECT unidad_organizacional_id FROM intervencion.plan "
        " WHERE intervencion_id = %s", (intervencion,))
    if not plan:
        raise ErrorApi("INTERVENCION_NO_EXISTE",
                       f"No existe el plan de intervencion {intervencion}.", 422)

    nuevo_blob = archivos.guardar(contenido, sello)

    documento_id = f"DOC-{uuid.uuid4().hex[:12].upper()}"
    ahora = dt.datetime.now(dt.timezone.utc)
    contenido_meta = {
        "clase": "EVIDENCIA_ARCHIVO",
        "intervencion_id": intervencion,
        "nombre_archivo": nombre,
        "extension": extension,
        "tipo_mime": archivos.TIPOS_MIME.get(extension, "application/octet-stream"),
        "bytes": len(contenido),
        "sha256": sello,
        "descripcion": (cuerpo.get("descripcion") or "")[:500],
    }
    doc = {
        "documento_id": documento_id,
        "tipo": "EVIDENCIA_ARCHIVO",
        "version": 1,
        "seudonimo_id": None,
        "unidad_organizacional_id": plan["unidad_organizacional_id"],
        "campania_id": None,
        "contenido": contenido_meta,
        "hash_contenido": sello,
        "etiquetas": ["evidencia", "archivo", extension],
        "creado_por": (g.actor or {}).get("sub"),
        "fecha_creacion": ahora,
        "fecha_actualizacion": ahora,
    }
    verificar_sin_identidad(doc)
    base()["documentos"].insert_one(doc)

    _bitacora("EVIDENCIA_CARGADA", "EXITO", recurso=documento_id)
    return responder({"documento_id": documento_id,
                      "sha256": sello,
                      "nombre_archivo": nombre,
                      "bytes": len(contenido),
                      "tipo_mime": contenido_meta["tipo_mime"],
                      # Dice si el blob era nuevo: subir dos veces el mismo
                      # archivo no lo duplica, y quien lo sube merece saber
                      # que pasó eso en lugar de creer que se guardó aparte.
                      "archivo_nuevo": nuevo_blob,
                      "fecha_creacion": ahora.isoformat()},
                     201, raiz="documento_creado")


@app.get(f"{BASE}/archivos/<sha256>/url")
@requiere_permiso("INTERVENCION_SEGUIMIENTO", "INTERVENCION_APROBAR",
                  "CONSENT_EVIDENCIA_AUDIT", "BITACORA_CONSULTAR")
def url_de_archivo(sha256):
    """Dirección temporal para un archivo privado del bucket.

    Solo existe cuando el servicio tiene GCS_BUCKET y la llave de firma.
    En developer no hay bucket: se responde 409 y el cliente usa la
    descarga directa.
    """
    limite_consumo(maximo=60)
    if not re.fullmatch(r"[0-9a-f]{64}", sha256 or ""):
        raise ErrorApi("PARAMETRO_INVALIDO",
                       "El sello tiene que ser un SHA-256 en hexadecimal.", 400)
    url = archivos.url_firmada(sha256)
    if not url:
        raise ErrorApi(
            "URL_NO_DISPONIBLE",
            "Este ambiente no firma direcciones. El archivo se descarga "
            "por el servicio.", 409)
    _bitacora("EVIDENCIA_DESCARGADA", "EXITO", recurso=sha256)
    return responder({"sha256": sha256, "url": url, "expira_en_segundos": 600},
                     200, raiz="url_firmada")


@app.get(f"{BASE}/archivos/<sha256>")
@requiere_permiso("INTERVENCION_SEGUIMIENTO", "INTERVENCION_APROBAR",
                  "CONSENT_EVIDENCIA_AUDIT", "BITACORA_CONSULTAR")
def descargar_archivo(sha256):
    """Recuperación controlada: comprueba el permiso, el sello, y registra.

    La descarga se registra y la carga también, pero la que importa para
    una revisión es esta: cargar es trabajo normal, descargar es el momento
    en que la información sale del sistema.
    """
    limite_consumo(maximo=60)
    if not re.fullmatch(r"[0-9a-f]{64}", sha256 or ""):
        raise ErrorApi("PARAMETRO_INVALIDO",
                       "El sello tiene que ser un SHA-256 en hexadecimal.", 400)

    registro = base()["documentos"].find_one({"hash_contenido": sha256,
                                              "tipo": "EVIDENCIA_ARCHIVO"})
    if not registro:
        raise ErrorApi("NO_ENCONTRADO",
                       "No hay ninguna evidencia registrada con ese sello.", 404)

    meta = registro.get("contenido") or {}
    try:
        contenido = archivos.leer(sha256)
    except ErrorApi:
        _bitacora("EVIDENCIA_DESCARGADA", "ERROR_TECNICO", recurso=sha256)
        raise

    _bitacora("EVIDENCIA_DESCARGADA", "EXITO", recurso=sha256)
    from flask import Response
    return Response(
        contenido, 200,
        {"Content-Type": meta.get("tipo_mime", "application/octet-stream"),
         "Content-Disposition":
             f'attachment; filename="{meta.get("nombre_archivo", sha256)}"',
         "Content-Length": str(len(contenido)),
         # El sello viaja con el archivo: quien lo reciba puede
         # confrontarlo sin volver a pedir nada.
         "X-Evidencia-Sello": sha256,
         "X-Content-Type-Options": "nosniff"})


# -------------------------------------------------------------- consulta
@app.get(BASE)
@requiere_permiso("CONSENT_EVIDENCIA_AUDIT", "BITACORA_CONSULTAR",
                  "INSTRUMENTO_ADMIN", "AGREGADO_GLOBAL")
def listar():
    limite_consumo()
    p, t = pagina()
    filtro = {}
    if request.args.get("tipo"):
        tipo = request.args["tipo"].strip().upper()
        if tipo not in TIPOS:
            raise ErrorApi("PARAMETRO_INVALIDO",
                           f"'tipo' debe ser uno de: {', '.join(sorted(TIPOS))}", 400)
        filtro["tipo"] = tipo
    if request.args.get("unidad"):
        filtro["unidad_organizacional_id"] = request.args["unidad"]
    if request.args.get("campania"):
        filtro["campania_id"] = request.args["campania"]
    if request.args.get("seudonimo"):
        filtro["seudonimo_id"] = request.args["seudonimo"]
    if request.args.get("etiqueta"):
        filtro["etiquetas"] = request.args["etiqueta"]

    col = base()["documentos"]
    total = col.count_documents(filtro)
    cursor_mongo = (col.find(filtro)
                       .sort("fecha_creacion", DESCENDING)
                       .skip((p - 1) * t).limit(t))
    documentos = [_limpiar(d) for d in cursor_mongo]

    _bitacora("BITACORA_CONSULTADA", "EXITO", tipo="DOCUMENTO")
    return responder(sobre_pagina(documentos, total, p, t, clave="documentos"),
                     200, raiz="documentos_respuesta")


@app.get(f"{BASE}/<documento_id>")
@requiere_permiso("CONSENT_EVIDENCIA_AUDIT", "BITACORA_CONSULTAR",
                  "INSTRUMENTO_ADMIN", "AGREGADO_GLOBAL")
def detalle(documento_id):
    limite_consumo()
    doc = base()["documentos"].find_one({"documento_id": documento_id})
    if not doc:
        raise ErrorApi("DOCUMENTO_NO_ENCONTRADO",
                       f"No existe el documento {documento_id}.", 404)
    _bitacora("BITACORA_CONSULTADA", "EXITO", recurso=documento_id)
    return responder(_limpiar(doc), 200, raiz="documento_respuesta")


# ----------------------------------------------------------- actualización
@app.put(f"{BASE}/<documento_id>")
@requiere_permiso("INSTRUMENTO_ADMIN", "PARAMETRO_ADMIN")
def actualizar(documento_id):
    limite_consumo(maximo=30)
    cuerpo = cuerpo_peticion()
    contenido = cuerpo.get("contenido")
    if not isinstance(contenido, dict) or not contenido:
        raise ErrorApi("VALIDACION", "La solicitud tiene campos invalidos.", 422,
                       [{"campo": "contenido", "problema": "debe ser un objeto no vacio"}])
    verificar_sin_identidad(cuerpo)

    col = base()["documentos"]
    actual = col.find_one({"documento_id": documento_id})
    if not actual:
        raise ErrorApi("DOCUMENTO_NO_ENCONTRADO",
                       f"No existe el documento {documento_id}.", 404)

    import json as _json
    huella = hashlib.sha256(
        _json.dumps(contenido, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()

    # Una evidencia de consentimiento NO se modifica: su valor como prueba
    # depende de que nadie la pueda cambiar despues del hecho.
    if actual["tipo"] == "EVIDENCIA_CONSENTIMIENTO":
        raise ErrorApi("DOCUMENTO_INMUTABLE",
                       "Una evidencia de consentimiento no se puede modificar. "
                       "Registra una nueva si el consentimiento cambio.", 409)

    col.update_one(
        {"documento_id": documento_id},
        {"$set": {"contenido": contenido, "hash_contenido": huella,
                  "fecha_actualizacion": dt.datetime.now(dt.timezone.utc),
                  "etiquetas": cuerpo.get("etiquetas", actual.get("etiquetas", []))},
         "$inc": {"version": 1}})

    _bitacora("CATALOGO_MODIFICADO", "EXITO", recurso=documento_id)
    return responder({"documento_id": documento_id,
                      "version": actual["version"] + 1,
                      "hash_contenido": huella},
                     200, raiz="documento_actualizado")


# ------------------------------------------------------------- agregación
@app.get(f"{BASE}/resumen")
@requiere_permiso("BITACORA_CONSULTAR", "AGREGADO_GLOBAL", "PARAMETRO_ADMIN")
def resumen():
    """Agregación de MongoDB: conteo por tipo y unidad.

    Cuenta documentos, no respuestas. No expone ningún valor de bienestar,
    de modo que no pasa por el mecanismo de privacidad diferencial: contar
    cuántas evidencias existe no dice nada de lo que alguien contestó.
    """
    limite_consumo()
    tuberia = [
        {"$group": {
            "_id": {"tipo": "$tipo", "unidad": "$unidad_organizacional_id"},
            "total": {"$sum": 1},
            "ultima": {"$max": "$fecha_creacion"},
        }},
        {"$sort": {"total": -1}},
        {"$limit": 50},
    ]
    filas = []
    for r in base()["documentos"].aggregate(tuberia):
        filas.append({
            "tipo": r["_id"].get("tipo"),
            "unidad_organizacional_id": r["_id"].get("unidad"),
            "total": r["total"],
            "ultima": r["ultima"].isoformat() if isinstance(r["ultima"], dt.datetime)
                      else r["ultima"],
        })
    return responder({"resumen": filas, "total_grupos": len(filas)},
                     200, raiz="resumen_respuesta")


# ------------------------------- recuperación por identificador relacionado
@app.get(f"{BASE}/por-campania/<campania_id>")
@requiere_permiso("BITACORA_CONSULTAR", "AGREGADO_GLOBAL", "INSTRUMENTO_ADMIN")
def por_campania(campania_id):
    """Cruza MongoDB con PostgreSQL por el identificador de campaña.

    Es el caso que pide la rúbrica: recuperación por identificadores
    relacionados entre las dos bases.
    """
    limite_consumo()
    campania = consultar_uno(
        "SELECT campania_id, nombre, estado, fecha_inicio, fecha_fin "
        "FROM catalogo.campania WHERE campania_id = %s", (campania_id,))
    if not campania:
        raise ErrorApi("CAMPANIA_NO_EXISTE",
                       f"La campania {campania_id} no existe en PostgreSQL.", 404)

    documentos = [_limpiar(d) for d in
                  base()["documentos"].find({"campania_id": campania_id})
                  .sort("fecha_creacion", DESCENDING).limit(100)]
    return responder({
        "campania": {k: (v.isoformat() if isinstance(v, (dt.date, dt.datetime)) else v)
                     for k, v in dict(campania).items()},
        "documentos": documentos,
        "total_documentos": len(documentos),
    }, 200, raiz="campania_documentos")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PUERTO", "8103")))
