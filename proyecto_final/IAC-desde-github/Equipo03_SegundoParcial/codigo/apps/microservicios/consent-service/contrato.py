"""Contrato OpenAPI de consent-service."""
from comun.openapi import PARAMS_PAGINACION, RESPUESTAS_ERROR, registrar_openapi

ESQUEMAS = {
    "CambioConsentimiento": {
        "type": "object",
        "required": ["estado"],
        "properties": {
            "estado": {"type": "string", "enum": ["ACEPTADO", "REVOCADO"],
                       "description": "Revocar inserta un evento nuevo. No borra el anterior."},
        },
    },
}

RUTAS = {
    "/api/v1/consentimiento/aviso": {"get": {
        "tags": ["Aviso"],
        "summary": "Aviso de privacidad vigente",
        "responses": dict({"200": {"description": "Aviso vigente"}}, **RESPUESTAS_ERROR)}},
    "/api/v1/consentimiento/avisos": {"get": {
        "tags": ["Aviso"],
        "summary": "Versiones del aviso",
        "parameters": PARAMS_PAGINACION,
        "responses": dict({"200": {"description": "Pagina de versiones"}}, **RESPUESTAS_ERROR)}},
    "/api/v1/consentimiento/mio": {"get": {
        "tags": ["Propio"],
        "summary": "Estado e historial de quien tiene la sesion",
        "description": "El seudonimo sale del token. No se acepta en la URL.",
        "responses": dict({"200": {"description": "Estado vigente e historial"}}, **RESPUESTAS_ERROR)}},
    "/api/v1/consentimiento": {"post": {
        "tags": ["Propio"],
        "summary": "Otorga o revoca el consentimiento propio",
        "requestBody": {"required": True, "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/CambioConsentimiento"},
                                 "example": {"estado": "REVOCADO"}},
            "application/xml": {"example":
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<solicitud xmlns="http://nexum.com.mx/bienestar/v1">\n'
                '  <estado>REVOCADO</estado>\n</solicitud>'}}},
        "responses": dict({"201": {"description": "Evento registrado, sin borrar el anterior"}},
                          **RESPUESTAS_ERROR)}},
    "/api/v1/consentimiento/evidencia": {"get": {
        "tags": ["Auditoria"],
        "summary": "Verifica que un seudonimo tenga consentimiento, sin ver respuestas",
        "parameters": [{"name": "seudonimo_id", "in": "query", "required": True,
                        "schema": {"type": "string"}}],
        "responses": dict({"200": {"description": "Estado vigente, sin empleado y sin respuestas"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Aviso", "description": "Texto versionado que la persona acepta."},
    {"name": "Propio", "description": "Solo el consentimiento de la sesion."},
    {"name": "Auditoria", "description": "Evidencia de que se consintio, no de que se respondio."},
]


def montar(app):
    return registrar_openapi(
        app, "consent-service — Bienestar Nexum",
        "Aviso de privacidad, otorgamiento y revocacion.\n\n"
        "Revocar agrega un evento REVOCADO. No hay DELETE sobre el historial. "
        "El seudonimo no se acepta del cliente: se resuelve con el token.",
        RUTAS, ESQUEMAS, ETIQUETAS, puerto=8110)
