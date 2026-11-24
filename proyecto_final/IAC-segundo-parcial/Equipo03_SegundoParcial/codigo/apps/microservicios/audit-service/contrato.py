"""Contrato OpenAPI de audit-service."""
from comun.openapi import PARAMS_PAGINACION, RESPUESTAS_ERROR, registrar_openapi

RUTAS = {
    "/api/v1/auditoria": {"get": {
        "tags": ["Bitacora"],
        "summary": "Eventos de acceso, sin contenido de respuestas",
        "parameters": PARAMS_PAGINACION + [
            {"name": "correlacion_id", "in": "query", "schema": {"type": "string"}},
            {"name": "accion", "in": "query", "schema": {"type": "string"}},
            {"name": "actor_usuario_id", "in": "query", "schema": {"type": "string"}},
            {"name": "resultado", "in": "query", "schema": {"type": "string"}},
            {"name": "desde", "in": "query", "schema": {"type": "string", "format": "date-time"}},
            {"name": "hasta", "in": "query", "schema": {"type": "string", "format": "date-time"}},
        ],
        "responses": dict({"200": {"description": "Pagina de eventos. La consulta queda registrada"}},
                          **RESPUESTAS_ERROR)}},
    "/api/v1/auditoria/correlacion/{correlacion_id}": {"get": {
        "tags": ["Bitacora"],
        "summary": "Todos los eventos de una misma operacion",
        "parameters": [{"name": "correlacion_id", "in": "path", "required": True,
                        "schema": {"type": "string"}}],
        "responses": dict({"200": {"description": "Secuencia de la correlacion"}},
                          **RESPUESTAS_ERROR)}},
    "/api/v1/auditoria/mios": {"get": {
        "tags": ["Transparencia"],
        "summary": "Accesos relacionados con la persona de la sesion",
        "parameters": PARAMS_PAGINACION,
        "responses": dict({"200": {"description": "Quien consulto, sin el contenido"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Bitacora", "description": "Quien, que, cuando, con que resultado."},
    {"name": "Transparencia", "description": "Lo que la persona puede ver sobre si misma."},
]


def montar(app):
    return registrar_openapi(
        app, "audit-service — Bienestar Nexum",
        "Bitacora centralizada. No guarda respuestas. "
        "Consultarla tambien queda en la bitacora. No hay borrado.",
        RUTAS, {}, ETIQUETAS, puerto=8118)
