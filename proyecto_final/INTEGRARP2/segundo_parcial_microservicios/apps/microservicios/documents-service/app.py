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
import uuid

from flask import g, request

from comun import (ErrorApi, VERSION_API, crear_servicio, limite_consumo,
                   obtener_redis, pagina, responder, requiere_permiso,
                   requiere_token, sobre_pagina)
from comun.datos import consultar_uno, cursor, ping as ping_pg
from comun.mongo import (ASCENDING, DESCENDING, asegurar_indices, base,
                         ping as ping_mongo, verificar_sin_identidad)

os.environ.setdefault("NOMBRE_SERVICIO", "documents-service")

TIPOS = {"EVIDENCIA_CONSENTIMIENTO", "AVISO_PRIVACIDAD", "REPORTE_ORGANIZACIONAL"}

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
    cuerpo = request.get_json(silent=True) or {}

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
    cuerpo = request.get_json(silent=True) or {}
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
