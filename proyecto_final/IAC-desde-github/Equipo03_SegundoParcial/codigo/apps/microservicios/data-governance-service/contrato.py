"""Contrato OpenAPI de data-governance-service."""
from comun.openapi import RESPUESTAS_ERROR, registrar_openapi

ESQUEMAS = {
    "SolicitudBaja": {
        "type": "object",
        "required": ["dato", "motivo"],
        "properties": {
            "dato": {"type": "string", "example": "Respuestas del autoreporte"},
            "motivo": {"type": "string", "minLength": 8,
                       "example": "Vencio el plazo declarado en el aviso."},
        },
    },
}

RUTAS = {
    "/api/v1/gobernanza/minimizacion": {"get": {
        "tags": ["Matriz"],
        "summary": "Que se captura y que esta prohibido",
        "responses": dict({"200": {"description": "Matriz de minimizacion"}},
                          **RESPUESTAS_ERROR)}},
    "/api/v1/gobernanza/retencion": {"get": {
        "tags": ["Retencion"],
        "summary": "Plazos del aviso vigente y de cada dato capturado",
        "responses": dict({"200": {"description": "Politica de retencion"}},
                          **RESPUESTAS_ERROR)}},
    "/api/v1/gobernanza/garantias": {"get": {
        "tags": ["Garantias"],
        "summary": "Resultado real de gobernanza.fn_verificar_garantias",
        "responses": dict({"200": {"description": "Cada garantia, cumplida o no"}},
                          **RESPUESTAS_ERROR)}},
    "/api/v1/gobernanza/baja": {"post": {
        "tags": ["Baja"],
        "summary": "Registra una baja. No borra el dato",
        "requestBody": {"required": True, "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/SolicitudBaja"}},
            "application/xml": {"example":
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<solicitud xmlns="http://nexum.com.mx/bienestar/v1">\n'
                '  <dato>Respuestas del autoreporte</dato>\n'
                '  <motivo>Vencio el plazo declarado en el aviso.</motivo>\n'
                '</solicitud>'}}},
        "responses": dict({"201": {"description": "Baja registrada, borrado en false"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Matriz", "description": "Datos capturados y datos prohibidos."},
    {"name": "Retencion", "description": "Cuanto tiempo permanece cada dato."},
    {"name": "Garantias", "description": "Comprobacion del modelo, no de la pantalla."},
    {"name": "Baja", "description": "Se anota. No se ejecuta el DELETE."},
]


def montar(app):
    return registrar_openapi(
        app, "data-governance-service — Bienestar Nexum",
        "Ciclo de vida, retencion, minimizacion y baja.\n\n"
        "La baja queda en la bitacora con borrado=false. El plazo lo marca el aviso.",
        RUTAS, ESQUEMAS, ETIQUETAS, puerto=8119)
