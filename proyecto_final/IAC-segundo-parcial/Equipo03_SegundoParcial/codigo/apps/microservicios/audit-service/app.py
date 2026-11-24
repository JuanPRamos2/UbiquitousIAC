"""
audit-service — bitácora de accesos, con el identificador de correlación.

Puerto 8118. Juan Pablo Ramos (#610248).

La bitácora no guarda el contenido de una respuesta. Guarda quién, qué
acción, sobre qué recurso, con qué resultado y con qué correlación. Con
el mismo correlacion_id se sigue una operación que pasó por varios
servicios: el encabezado X-Correlacion-Id viaja en la respuesta de todos.

Consultar la bitácora también se registra (BITACORA_CONSULTADA). Si esa
consulta no dejara rastro, el auditor sería el único perfil invisible.

No hay DELETE ni UPDATE. 09_permisos.sh no otorga esos privilegios, y
este servicio no los pide.
"""
import os

from flask import g, request

from comun import (ErrorApi, VERSION_API, crear_servicio, limite_consumo,
                   pagina, responder, requiere_permiso, sobre_pagina)
from comun.datos import consultar, consultar_uno, cursor, ping as ping_pg
from comun.seguridad import obtener_redis

os.environ.setdefault("NOMBRE_SERVICIO", "audit-service")


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "audit-service",
    "Bitacora de accesos y seguimiento por correlacion",
    comprobaciones={"postgresql": ping_pg, "redis": _ping_redis})

from contrato import montar as _montar_contrato
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/auditoria"


def _limpiar(fila):
    import datetime as dt
    salida = {}
    for clave, valor in dict(fila).items():
        if isinstance(valor, dt.datetime):
            salida[clave] = valor.isoformat()
        else:
            salida[clave] = valor
    return salida


def _registrar_consulta(resultado, recurso=None):
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO auditoria.bitacora (actor_usuario_id, actor_perfil, "
                " accion, tipo_recurso, recurso_id, resultado, correlacion_id) "
                "VALUES (%s,%s,'BITACORA_CONSULTADA','BITACORA',%s,%s,%s)",
                ((g.get("actor") or {}).get("sub"),
                 ((g.get("actor") or {}).get("perfil") or "ANONIMO")[:30],
                 None if recurso is None else str(recurso)[:80],
                 resultado, (getattr(g, "correlacion_id", "") or "")[:60]))
    except Exception:
        app.logger.exception("No se pudo escribir la consulta de bitacora")


def _filtros():
    condiciones = []
    params = []
    correlacion = (request.args.get("correlacion_id") or "").strip()
    accion = (request.args.get("accion") or "").strip()
    actor = (request.args.get("actor_usuario_id") or "").strip()
    resultado = (request.args.get("resultado") or "").strip()
    desde = (request.args.get("desde") or "").strip()
    hasta = (request.args.get("hasta") or "").strip()
    if correlacion:
        condiciones.append("correlacion_id = %s")
        params.append(correlacion)
    if accion:
        condiciones.append("accion = %s")
        params.append(accion)
    if actor:
        condiciones.append("actor_usuario_id = %s")
        params.append(actor)
    if resultado:
        condiciones.append("resultado = %s")
        params.append(resultado)
    if desde:
        condiciones.append("fecha_hora >= %s")
        params.append(desde)
    if hasta:
        condiciones.append("fecha_hora <= %s")
        params.append(hasta)
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return where, tuple(params)


@app.get(BASE)
@requiere_permiso("BITACORA_CONSULTAR")
def listar():
    limite_consumo()
    p, t = pagina()
    where, params = _filtros()
    total = consultar_uno(
        f"SELECT COUNT(*) AS n FROM auditoria.bitacora {where}", params)["n"]
    filas = consultar(
        "SELECT bitacora_id, fecha_hora, actor_usuario_id, actor_perfil, accion, "
        "       tipo_recurso, recurso_id, resultado, correlacion_id "
        f"FROM auditoria.bitacora {where} "
        "ORDER BY fecha_hora DESC, bitacora_id DESC LIMIT %s OFFSET %s",
        params + (t, (p - 1) * t))
    _registrar_consulta("EXITO")
    return responder(sobre_pagina([_limpiar(f) for f in filas], total, p, t, "eventos"),
                     raiz="bitacora_respuesta")


@app.get(f"{BASE}/correlacion/<correlacion_id>")
@requiere_permiso("BITACORA_CONSULTAR")
def por_correlacion(correlacion_id):
    limite_consumo()
    if not correlacion_id or len(correlacion_id) > 60:
        raise ErrorApi("PARAMETRO_INVALIDO", "correlacion_id invalido.", 400)
    filas = consultar(
        "SELECT bitacora_id, fecha_hora, actor_usuario_id, actor_perfil, accion, "
        "       tipo_recurso, recurso_id, resultado, correlacion_id "
        "FROM auditoria.bitacora WHERE correlacion_id = %s "
        "ORDER BY fecha_hora, bitacora_id",
        (correlacion_id,))
    if not filas:
        _registrar_consulta("RECHAZADO", correlacion_id)
        raise ErrorApi("NO_ENCONTRADO",
                       "No hay eventos con esa correlacion.", 404)
    _registrar_consulta("EXITO", correlacion_id)
    return responder({
        "correlacion_id": correlacion_id,
        "eventos": [_limpiar(f) for f in filas],
        "total": len(filas),
    }, raiz="correlacion_respuesta")


@app.get(f"{BASE}/mios")
@requiere_permiso("PARTICIPACION_PROPIA")
def mios():
    """Lo que el aviso promete: la persona ve quién consultó lo suyo."""
    limite_consumo()
    p, t = pagina()
    total = consultar_uno(
        "SELECT COUNT(*) AS n FROM portal.v_accesos_a_mis_datos WHERE usuario_id = %s",
        (g.actor.get("sub"),))["n"]
    filas = consultar(
        "SELECT fecha_hora, actor_perfil, que_hizo, resultado "
        "FROM portal.v_accesos_a_mis_datos WHERE usuario_id = %s "
        "ORDER BY fecha_hora DESC LIMIT %s OFFSET %s",
        (g.actor.get("sub"), t, (p - 1) * t))
    return responder(sobre_pagina([_limpiar(f) for f in filas], total, p, t, "accesos"),
                     raiz="accesos_respuesta")
