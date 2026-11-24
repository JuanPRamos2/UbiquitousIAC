"""
Documentación OpenAPI servida por cada microservicio.

Los cuatro servicios comparten la mitad de su contrato: el esquema de
seguridad, el sobre de error, los parámetros de paginación y los códigos
HTTP. Escribir eso cuatro veces a mano garantiza que se desincronice, así
que aquí vive la parte común y cada servicio aporta solo lo suyo.

Cada servicio expone:
    GET /openapi.json   el contrato
    GET /docs           Swagger UI

Swagger UI se sirve desde el propio servicio, no desde un CDN: si la red
de la demostración bloquea el CDN, la documentación igual abre.
"""
import os

from flask import Blueprint, jsonify, render_template_string

ESPACIO_XML = "http://nexum.com.mx/bienestar/v1"

RESPUESTAS_ERROR = {
    "400": {"$ref": "#/components/responses/SolicitudInvalida"},
    "401": {"$ref": "#/components/responses/NoAutenticado"},
    "403": {"$ref": "#/components/responses/SinPermiso"},
    "404": {"$ref": "#/components/responses/NoEncontrado"},
    "422": {"$ref": "#/components/responses/ValidacionFallida"},
    "429": {"$ref": "#/components/responses/LimiteExcedido"},
    "500": {"$ref": "#/components/responses/ErrorInterno"},
}

PARAMS_PAGINACION = [
    {"name": "pagina", "in": "query", "required": False,
     "schema": {"type": "integer", "minimum": 1, "default": 1},
     "description": "Numero de pagina, empezando en 1."},
    {"name": "tamano", "in": "query", "required": False,
     "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
     "description": "Elementos por pagina. El tope de 100 evita que una sola "
                    "peticion pida un volumen que tumbe el servicio."},
    {"name": "formato", "in": "query", "required": False,
     "schema": {"type": "string", "enum": ["json", "xml"]},
     "description": "Alternativa al encabezado Accept, util para probar "
                    "desde el navegador."},
]


def _componentes_comunes():
    error = {
        "type": "object",
        "required": ["error"],
        "properties": {"error": {
            "type": "object",
            "required": ["codigo", "mensaje"],
            "properties": {
                "codigo": {"type": "string",
                           "description": "Codigo estable; el cliente programa "
                                          "contra esto, no contra el mensaje.",
                           "example": "SIN_PERMISO"},
                "mensaje": {"type": "string",
                            "example": "El perfil Colaborador no tiene el permiso requerido."},
                "detalles": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"campo": {"type": "string", "example": "correo"},
                                   "problema": {"type": "string",
                                                "example": "no es un correo valido"}}}},
                "correlacion_id": {"type": "string", "example": "a1b2c3d4e5f60718"},
            }}}}

    def respuesta(desc, codigo_ejemplo, mensaje_ejemplo):
        ejemplo = {"error": {"codigo": codigo_ejemplo, "mensaje": mensaje_ejemplo,
                             "detalles": [], "correlacion_id": "a1b2c3d4e5f60718"}}
        return {"description": desc, "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/Error"},
                                 "example": ejemplo},
            "application/xml": {"schema": {"$ref": "#/components/schemas/Error"},
                                "example": (
                                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                                    f'<error_respuesta xmlns="{ESPACIO_XML}">\n'
                                    f'  <error>\n'
                                    f'    <codigo>{codigo_ejemplo}</codigo>\n'
                                    f'    <mensaje>{mensaje_ejemplo}</mensaje>\n'
                                    f'    <detalles/>\n'
                                    f'    <correlacion_id>a1b2c3d4e5f60718</correlacion_id>\n'
                                    f'  </error>\n'
                                    f'</error_respuesta>')}}}

    return {
        "securitySchemes": {"bearerAuth": {
            "type": "http", "scheme": "bearer", "bearerFormat": "JWT",
            "description": "Token emitido por auth-service o por el sistema web. "
                           "Ambos firman con el mismo secreto y comparten Redis, "
                           "de modo que un cierre de sesion revoca en todos los "
                           "componentes."}},
        "schemas": {
            "Error": error,
            "Paginacion": {"type": "object", "properties": {
                "pagina": {"type": "integer", "example": 1},
                "tamano": {"type": "integer", "example": 20},
                "total": {"type": "integer", "example": 143},
                "total_paginas": {"type": "integer", "example": 8},
                "tiene_siguiente": {"type": "boolean", "example": True},
                "tiene_anterior": {"type": "boolean", "example": False}}},
        },
        "responses": {
            "SolicitudInvalida": respuesta(
                "Parametro mal formado.", "PARAMETRO_INVALIDO",
                "'tamano' debe estar entre 1 y 100."),
            "NoAutenticado": respuesta(
                "Falta el token, es invalido, expiro o la sesion fue revocada.",
                "SESION_REVOCADA", "La sesion fue cerrada o revocada."),
            "SinPermiso": respuesta(
                "El perfil no tiene el permiso necesario.", "SIN_PERMISO",
                "El perfil Colaborador no tiene ninguno de los permisos requeridos."),
            "NoEncontrado": respuesta(
                "El recurso no existe.", "RECURSO_NO_ENCONTRADO",
                "La ruta solicitada no existe en este servicio."),
            "ValidacionFallida": respuesta(
                "La solicitud trae campos invalidos. Se devuelven TODOS los "
                "problemas de una vez, no solo el primero.",
                "VALIDACION", "La solicitud tiene campos invalidos."),
            "LimiteExcedido": respuesta(
                "Se rebaso el limite de consumo.", "LIMITE_EXCEDIDO",
                "Mas de 120 peticiones por 60 segundos."),
            "ErrorInterno": respuesta(
                "Falla no prevista. Fuera de developer no se devuelve el detalle.",
                "ERROR_INTERNO", "Error interno del servicio. El evento quedo registrado."),
        },
    }


PLANTILLA_DOCS = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ titulo }} — contrato</title>
<link rel="stylesheet" href="{{ base }}/estaticos/swagger/swagger-ui.css">
<style>body{margin:0} .topbar{display:none}</style>
</head>
<body>
<div id="swagger"></div>
<script src="{{ base }}/estaticos/swagger/swagger-ui-bundle.js"></script>
<script>
  window.ui = SwaggerUIBundle({
    url: "{{ base }}/openapi.json",
    dom_id: "#swagger",
    deepLinking: true,
    displayRequestDuration: true,
    tryItOutEnabled: true,
    persistAuthorization: true
  });
</script>
</body>
</html>"""


def registrar_openapi(app, titulo, descripcion, rutas, esquemas=None,
                      etiquetas=None, puerto=8000):
    """Monta /openapi.json y /docs en el servicio."""
    import os as _os
    bp = Blueprint("openapi", __name__,
                   static_folder=_os.path.join(_os.path.dirname(__file__), "estaticos"),
                   static_url_path="/estaticos")
    componentes = _componentes_comunes()
    componentes["schemas"].update(esquemas or {})

    contrato = {
        "openapi": "3.0.3",
        "info": {
            "title": titulo,
            "version": "1.0.0",
            "description": descripcion,
            "contact": {"name": "Equipo 03 — Proyecto 4",
                        "email": "equipo03@udem.edu.mx"},
        },
        "servers": [
            {"url": f"http://localhost:{puerto}", "description": "developer"},
            {"url": "https://api.bienestar-nexum.mx", "description": "production"},
        ],
        "tags": etiquetas or [],
        "security": [{"bearerAuth": []}],
        "paths": rutas,
        "components": componentes,
    }

    @bp.get("/openapi.json")
    def _contrato():
        return jsonify(contrato)

    @bp.get("/docs")
    def _docs():
        from flask import request
        return render_template_string(PLANTILLA_DOCS, titulo=titulo,
                                      base=request.script_root or "")

    app.register_blueprint(bp)
    return contrato
