"""
Registro de auditoría.

Una bitácora que se escribe "cuando conviene" no sirve como evidencia. Por
eso este módulo registra también los intentos fallidos y los rechazos: el
documento de análisis lo pide de forma explícita en la decisión D-05.

El identificador de correlación permite seguir una misma petición a través
de la bitácora cuando una acción del usuario produce varios registros.
"""
import logging
import uuid

from flask import g, request

from .datos import cursor

log = logging.getLogger(__name__)


def correlacion() -> str:
    if not hasattr(g, "correlacion_id"):
        g.correlacion_id = uuid.uuid4().hex[:16]
    return g.correlacion_id


def registrar(accion: str, resultado: str = "EXITO", *,
              tipo_recurso: str = None, recurso: str = None,
              actor: str = None, perfil: str = None):
    """Escribe una línea de bitácora. Nunca interrumpe la operación.

    Si la escritura falla, se deja constancia en la bitácora técnica del
    servicio en lugar de propagar el error: perder una línea de auditoría
    es malo, pero tumbar la operación del usuario por eso sería peor, y
    el fallo queda visible para operación.
    """
    sesion = g.get("sesion") or {}
    actor_id = actor if actor is not None else sesion.get("sub")
    actor_perfil = perfil or sesion.get("perfil") or "ANONIMO"
    origen = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    origen = origen.split(",")[0].strip() or None

    try:
        with cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO auditoria.bitacora
                    (actor_usuario_id, actor_perfil, accion, tipo_recurso,
                     recurso_id, resultado, correlacion_id, direccion_origen)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (actor_id, actor_perfil[:30], accion, tipo_recurso,
                 recurso[:80] if recurso else None, resultado,
                 correlacion(), origen))
    except Exception as e:
        log.error("No se pudo escribir en la bitácora (%s / %s): %s",
                  accion, resultado, e)
