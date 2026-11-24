"""
consent-service — aviso de privacidad, otorgamiento y revocación.

Puerto 8110. Juan Pablo Ramos (#610248).

Tres decisiones, y la consecuencia de cada una:

1. Revocar no borra. Se inserta otra fila con estado REVOCADO. El estado
   vigente es el evento más reciente (vista consentimiento.v_estado_vigente).
   Borrar el consentimiento anterior dejaría sin evidencia de que alguna
   vez se otorgó.

2. El seudónimo lo resuelve el servicio con el usuario del token, leyendo
   portal.v_participacion_propia. Si el cliente pudiera mandar el
   seudónimo, podría aceptar o revocar en nombre de otra persona.

3. Este servicio no lee consentimiento.seudonimo. Esa tabla es la que
   permite reidentificar, y el rol de la aplicación no tiene permiso
   sobre ella. La vista del portal ya contesta «quién soy» sin abrirla.
"""
import os

from flask import g, request

from comun import (ErrorApi, VERSION_API, crear_servicio, cuerpo_peticion,
                   limite_consumo, pagina, responder, requiere_permiso,
                   sobre_pagina)
from comun.datos import consultar, consultar_uno, cursor, ping as ping_pg
from comun.seguridad import obtener_redis

os.environ.setdefault("NOMBRE_SERVICIO", "consent-service")

PROHIBIDOS = {"empleado_id", "seudonimo_id", "correo", "nombre",
              "numero_empleado", "curp", "rfc"}


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "consent-service",
    "Aviso de privacidad versionado, consentimiento y revocacion",
    comprobaciones={"postgresql": ping_pg, "redis": _ping_redis})

from contrato import montar as _montar_contrato
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/consentimiento"


def _bitacora(accion, resultado, recurso=None):
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO auditoria.bitacora (actor_usuario_id, actor_perfil, "
                " accion, tipo_recurso, recurso_id, resultado, correlacion_id) "
                "VALUES (%s,%s,%s,'CONSENTIMIENTO',%s,%s,%s)",
                ((g.get("actor") or {}).get("sub"),
                 ((g.get("actor") or {}).get("perfil") or "ANONIMO")[:30],
                 accion, None if recurso is None else str(recurso)[:80],
                 resultado, (getattr(g, "correlacion_id", "") or "")[:60]))
    except Exception:
        app.logger.exception("No se pudo escribir en la bitacora: %s", accion)


def _limpiar(fila):
    import datetime as dt
    from decimal import Decimal
    salida = {}
    for clave, valor in dict(fila).items():
        if isinstance(valor, Decimal):
            salida[clave] = int(valor) if valor == valor.to_integral_value() else float(valor)
        elif isinstance(valor, (dt.datetime, dt.date)):
            salida[clave] = valor.isoformat()
        else:
            salida[clave] = valor
    return salida


def _rechazar_identidad(cuerpo):
    presentes = [k for k in cuerpo if str(k).lower() in PROHIBIDOS]
    if presentes:
        raise ErrorApi(
            "CAMPO_PROHIBIDO",
            "La identidad no viaja en el cuerpo. El servicio la toma del token.",
            422, [{"campo": k, "problema": "no se acepta del cliente"} for k in presentes])


def _mio():
    fila = consultar_uno(
        "SELECT seudonimo_id, estado_consentimiento, fecha_consentimiento "
        "FROM portal.v_participacion_propia WHERE usuario_id = %s",
        (g.actor.get("sub"),))
    if not fila or not fila.get("seudonimo_id"):
        raise ErrorApi(
            "SIN_SEUDONIMO",
            "Esta cuenta no tiene seudonimo operativo. Sin eso no hay "
            "consentimiento que registrar.", 403)
    return fila


def _aviso_vigente():
    aviso = consultar_uno(
        "SELECT * FROM consentimiento.aviso_privacidad "
        "WHERE vigente ORDER BY version DESC LIMIT 1")
    if not aviso:
        raise ErrorApi(
            "AVISO_NO_CONFIGURADO",
            "No hay un aviso de privacidad vigente. Sin aviso no se puede "
            "otorgar ni revocar.", 503)
    return aviso


@app.get(f"{BASE}/aviso")
@requiere_permiso("AVISO_CONSULTAR")
def aviso_vigente():
    limite_consumo()
    aviso = _limpiar(_aviso_vigente())
    _bitacora("AVISO_CONSULTADO", "EXITO", aviso.get("aviso_id"))
    return responder({"aviso": aviso}, raiz="aviso_respuesta")


@app.get(f"{BASE}/avisos")
@requiere_permiso("AVISO_CONSULTAR")
def avisos():
    limite_consumo()
    p, t = pagina()
    total = consultar_uno("SELECT COUNT(*) AS n FROM consentimiento.aviso_privacidad")["n"]
    filas = consultar(
        "SELECT aviso_id, version, fecha_vigencia, fecha_fin_vigencia, vigente "
        "FROM consentimiento.aviso_privacidad "
        "ORDER BY fecha_vigencia DESC LIMIT %s OFFSET %s",
        (t, (p - 1) * t))
    return responder(sobre_pagina([_limpiar(f) for f in filas], total, p, t, "avisos"),
                     raiz="avisos_respuesta")


@app.get(f"{BASE}/mio")
@requiere_permiso("CONSENT_HISTORIAL_PROPIO")
def mio():
    limite_consumo()
    propio = _mio()
    historial = consultar(
        "SELECT consentimiento_id, aviso_id, estado, fecha_evento "
        "FROM consentimiento.consentimiento WHERE seudonimo_id = %s "
        "ORDER BY fecha_evento DESC, consentimiento_id DESC",
        (propio["seudonimo_id"],))
    return responder({
        "seudonimo_id": propio["seudonimo_id"],
        "estado": propio["estado_consentimiento"],
        "fecha_estado": _limpiar(propio).get("fecha_consentimiento"),
        "historial": [_limpiar(f) for f in historial],
    }, raiz="consentimiento_respuesta")


@app.post(BASE)
@requiere_permiso("CONSENT_OTORGAR", "CONSENT_REVOCAR")
def cambiar():
    limite_consumo(maximo=30)
    cuerpo = cuerpo_peticion()
    _rechazar_identidad(cuerpo)
    estado = (cuerpo.get("estado") or "").strip().upper()
    if estado not in ("ACEPTADO", "REVOCADO"):
        raise ErrorApi(
            "VALIDACION", "El estado debe ser ACEPTADO o REVOCADO.", 422,
            [{"campo": "estado", "problema": "valor no permitido"}])
    permiso = "CONSENT_OTORGAR" if estado == "ACEPTADO" else "CONSENT_REVOCAR"
    if permiso not in g.permisos:
        raise ErrorApi(
            "SIN_PERMISO",
            f"Para registrar {estado} hace falta el permiso {permiso}.", 403)

    propio = _mio()
    aviso = _aviso_vigente()
    vigente = consultar_uno(
        "SELECT estado FROM consentimiento.v_estado_vigente WHERE seudonimo_id = %s",
        (propio["seudonimo_id"],))
    if vigente and vigente["estado"] == estado:
        raise ErrorApi(
            "YA_REGISTRADO",
            f"El consentimiento ya esta en estado {estado}. Revocar no se "
            f"hace borrando la fila anterior: si quisieras el otro estado, "
            f"manda ese.", 409)

    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO consentimiento.consentimiento (seudonimo_id, aviso_id, estado) "
            "VALUES (%s, %s, %s) RETURNING consentimiento_id, fecha_evento",
            (propio["seudonimo_id"], aviso["aviso_id"], estado))
        creada = dict(cur.fetchone())

    accion = "CONSENT_OTORGADO" if estado == "ACEPTADO" else "CONSENT_REVOCADO"
    _bitacora(accion, "EXITO", propio["seudonimo_id"])
    return responder({
        "consentimiento_id": creada["consentimiento_id"],
        "estado": estado,
        "aviso_id": aviso["aviso_id"],
        "fecha_evento": _limpiar(creada)["fecha_evento"],
        "borro_el_anterior": False,
    }, 201, raiz="consentimiento_respuesta")


@app.get(f"{BASE}/evidencia")
@requiere_permiso("CONSENT_EVIDENCIA_AUDIT")
def evidencia():
    """El auditor comprueba que hubo consentimiento. No ve respuestas ni empleado."""
    limite_consumo()
    seudonimo = (request.args.get("seudonimo_id") or "").strip()
    if not seudonimo:
        raise ErrorApi("PARAMETRO_INVALIDO", "Falta seudonimo_id.", 400)
    vigente = consultar_uno(
        "SELECT seudonimo_id, aviso_id, estado, fecha_evento "
        "FROM consentimiento.v_estado_vigente WHERE seudonimo_id = %s",
        (seudonimo,))
    if not vigente:
        _bitacora("CONSENT_VERIFICADO", "RECHAZADO", seudonimo)
        raise ErrorApi("NO_ENCONTRADO",
                       "No hay consentimiento registrado para ese seudonimo.", 404)
    cuantos = consultar_uno(
        "SELECT COUNT(*) AS n FROM consentimiento.consentimiento WHERE seudonimo_id = %s",
        (seudonimo,))["n"]
    _bitacora("CONSENT_VERIFICADO", "EXITO", seudonimo)
    cuerpo = _limpiar(vigente)
    cuerpo["eventos"] = cuantos
    cuerpo["incluye_respuestas"] = False
    cuerpo["incluye_empleado"] = False
    return responder(cuerpo, raiz="evidencia_respuesta")
