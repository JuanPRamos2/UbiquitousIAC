"""Contrato OpenAPI de privacy-service."""
from comun.openapi import RESPUESTAS_ERROR, registrar_openapi

RUTAS = {
    "/api/v1/privacidad/politica": {"get": {
        "tags": ["Politica"],
        "summary": "Seudonimizacion, umbral k y donde NO se calcula el ruido",
        "responses": dict({"200": {"description": "Politica vigente"}}, **RESPUESTAS_ERROR)}},
    "/api/v1/privacidad/umbral": {"get": {
        "tags": ["Umbral"],
        "summary": "Valor actual de k",
        "description": "k sale de agregado.parametro_privacidad. Cambiarlo es "
                       "trabajo de configuration-service, no de este.",
        "responses": dict({"200": {"description": "Umbral k"}}, **RESPUESTAS_ERROR)}},
    "/api/v1/privacidad/seudonimo": {"get": {
        "tags": ["Seudonimo"],
        "summary": "Seudonimo de la sesion, no el de otra persona",
        "responses": dict({"200": {"description": "Seudonimo propio"}}, **RESPUESTAS_ERROR)}},
    "/api/v1/privacidad/publicacion": {"get": {
        "tags": ["Umbral"],
        "summary": "Si un resultado ya publicado alcanzo k",
        "description": "No cuenta respuestas individuales y no gasta epsilon. "
                       "Lee el estado que la funcion protegida ya dejo escrito.",
        "parameters": [
            {"name": "unidad_organizacional_id", "in": "query", "required": True,
             "schema": {"type": "string"}},
            {"name": "campania_id", "in": "query", "required": True,
             "schema": {"type": "string"}},
        ],
        "responses": dict({"200": {"description": "Estado de publicacion, sin n exacto"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Politica", "description": "Que se hace con los datos y como se nombra."},
    {"name": "Umbral", "description": "k minimo. Un grupo menor no se publica."},
    {"name": "Seudonimo", "description": "Identificador operativo de la propia sesion."},
]


def montar(app):
    return registrar_openapi(
        app, "privacy-service — Bienestar Nexum",
        "Seudonimizacion y umbral minimo k.\n\n"
        "No calcula ruido de Laplace ni descuenta epsilon. Eso esta en "
        "agregado.fn_ruido_laplace. Aqui se lee k y el estado ya publicado.",
        RUTAS, {}, ETIQUETAS, puerto=8111)
