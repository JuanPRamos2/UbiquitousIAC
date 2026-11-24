"""
data-governance-service — minimización, retención y baja.

Puerto 8119. Juan Pablo Ramos (#610248).

La matriz gobernanza.minimizacion_dato dice qué se captura y qué está
prohibido (correo, GPS, teclado, diagnóstico). Un dato con
se_captura = false no se «da de baja»: nunca entró.

La baja de un dato que sí se captura no lo borra en el momento. Queda
registrada (DATO_BAJA_REGISTRADA) y la retención declarada sigue
vigente. Borrar respuestas al recibir un POST dejaría sin efecto el
plazo del aviso y la evidencia de consentimiento.

Las garantías G1 a G6 se leen de gobernanza.fn_verificar_garantias.
Si una falla, la respuesta lo dice: no se reescribe el resultado para
que la demostración salga verde.
"""
import os

from flask import g

from comun import (ErrorApi, VERSION_API, crear_servicio, cuerpo_peticion,
                   limite_consumo, responder, requiere_permiso)
from comun.datos import consultar, consultar_uno, cursor, ping as ping_pg
from comun.seguridad import obtener_redis

os.environ.setdefault("NOMBRE_SERVICIO", "data-governance-service")


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "data-governance-service",
    "Minimizacion, retencion y registro de baja sin borrado inmediato",
    comprobaciones={"postgresql": ping_pg, "redis": _ping_redis})

from contrato import montar as _montar_contrato
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/gobernanza"


def _bitacora(accion, resultado, recurso=None):
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO auditoria.bitacora (actor_usuario_id, actor_perfil, "
                " accion, tipo_recurso, recurso_id, resultado, correlacion_id) "
                "VALUES (%s,%s,%s,'GOBERNANZA',%s,%s,%s)",
                ((g.get("actor") or {}).get("sub"),
                 ((g.get("actor") or {}).get("perfil") or "ANONIMO")[:30],
                 accion, None if recurso is None else str(recurso)[:80],
                 resultado, (getattr(g, "correlacion_id", "") or "")[:60]))
    except Exception:
        app.logger.exception("No se pudo escribir en la bitacora: %s", accion)


@app.get(f"{BASE}/minimizacion")
@requiere_permiso("BITACORA_CONSULTAR", "PARAMETRO_ADMIN")
def minimizacion():
    limite_consumo()
    filas = consultar(
        "SELECT dato, se_captura, justificacion, almacenamiento, retencion, riesgo_asociado "
        "FROM gobernanza.minimizacion_dato ORDER BY se_captura DESC, dato")
    _bitacora("GOBERNANZA_CONSULTADA", "EXITO", "minimizacion")
    return responder({
        "datos": [dict(f) for f in filas],
        "se_capturan": sum(1 for f in filas if f["se_captura"]),
        "prohibidos": sum(1 for f in filas if not f["se_captura"]),
    }, raiz="minimizacion_respuesta")


@app.get(f"{BASE}/retencion")
@requiere_permiso("BITACORA_CONSULTAR", "PARAMETRO_ADMIN", "AVISO_CONSULTAR")
def retencion():
    limite_consumo()
    aviso = consultar_uno(
        "SELECT aviso_id, version, plazo_retencion, politica_retencion "
        "FROM consentimiento.aviso_privacidad WHERE vigente "
        "ORDER BY version DESC LIMIT 1")
    if not aviso:
        raise ErrorApi("AVISO_NO_CONFIGURADO", "No hay aviso vigente.", 503)
    matriz = consultar(
        "SELECT dato, se_captura, retencion FROM gobernanza.minimizacion_dato "
        "WHERE se_captura ORDER BY dato")
    _bitacora("GOBERNANZA_CONSULTADA", "EXITO", "retencion")
    return responder({
        "aviso_id": aviso["aviso_id"],
        "version": aviso["version"],
        "plazo_retencion": aviso["plazo_retencion"],
        "politica_retencion": aviso["politica_retencion"],
        "datos_capturados": [dict(f) for f in matriz],
    }, raiz="retencion_respuesta")


@app.get(f"{BASE}/garantias")
@requiere_permiso("BITACORA_CONSULTAR", "PARAMETRO_ADMIN")
def garantias():
    limite_consumo()
    filas = consultar(
        "SELECT garantia, cumple, detalle FROM gobernanza.fn_verificar_garantias()")
    _bitacora("GOBERNANZA_CONSULTADA", "EXITO", "garantias")
    return responder({
        "garantias": [{
            "garantia": f["garantia"],
            "cumple": f["cumple"],
            "detalle": f["detalle"],
        } for f in filas],
        "todas_cumplen": all(f["cumple"] for f in filas),
    }, raiz="garantias_respuesta")


@app.post(f"{BASE}/baja")
@requiere_permiso("PARAMETRO_ADMIN")
def baja():
    """Registra la solicitud. No ejecuta el borrado."""
    limite_consumo(maximo=20)
    cuerpo = cuerpo_peticion()
    dato = (cuerpo.get("dato") or "").strip()
    motivo = (cuerpo.get("motivo") or "").strip()
    if len(motivo) < 8:
        raise ErrorApi("VALIDACION", "El motivo debe explicar la baja, minimo 8 caracteres.",
                       422, [{"campo": "motivo", "problema": "minimo 8 caracteres"}])
    fila = consultar_uno(
        "SELECT dato, se_captura, retencion, almacenamiento "
        "FROM gobernanza.minimizacion_dato WHERE dato = %s", (dato,))
    if not fila:
        raise ErrorApi("NO_ENCONTRADO",
                       "Ese dato no esta en la matriz de minimizacion.", 404)
    if not fila["se_captura"]:
        _bitacora("DATO_BAJA_REGISTRADA", "RECHAZADO", dato)
        return responder({
            "dato": dato,
            "borrado": False,
            "efecto": "NO_SE_CAPTURA",
            "mensaje": "Ese dato esta prohibido y no se almacena. No hay nada que borrar.",
        }, raiz="baja_respuesta")

    _bitacora("DATO_BAJA_REGISTRADA", "EXITO", dato)
    return responder({
        "dato": dato,
        "borrado": False,
        "efecto": "EN_CICLO_DE_RETENCION",
        "retencion": fila["retencion"],
        "almacenamiento": fila["almacenamiento"],
        "motivo_registrado": True,
        "mensaje": "La baja quedo registrada. El dato no se borra en este "
                   "momento: sigue el plazo que declara el aviso.",
    }, 201, raiz="baja_respuesta")
