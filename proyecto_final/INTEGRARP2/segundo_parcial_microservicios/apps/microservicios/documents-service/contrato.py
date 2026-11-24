"""Contrato OpenAPI de documents-service."""
from comun.openapi import PARAMS_PAGINACION, RESPUESTAS_ERROR, registrar_openapi

ESQUEMAS = {
    "Documento": {
        "type": "object",
        "description": "Nota: este esquema NO admite empleado_id. El servicio "
                       "rechaza con 422 cualquier documento que lo traiga, "
                       "aunque venga anidado.",
        "properties": {
            "documento_id": {"type": "string", "pattern": "^DOC-[0-9A-F]{12}$"},
            "tipo": {"type": "string", "enum": ["EVIDENCIA_CONSENTIMIENTO",
                                               "AVISO_PRIVACIDAD",
                                               "REPORTE_ORGANIZACIONAL"]},
            "version": {"type": "integer", "minimum": 1},
            "seudonimo_id": {"type": "string", "nullable": True,
                             "pattern": "^SEUD-[0-9]{5}$",
                             "description": "Unico identificador de persona admitido."},
            "unidad_organizacional_id": {"type": "string", "nullable": True},
            "campania_id": {"type": "string", "nullable": True},
            "contenido": {"type": "object", "additionalProperties": True,
                          "description": "Forma libre: cada tipo de documento tiene "
                                         "la suya, y eso es lo que justifica MongoDB."},
            "hash_contenido": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "etiquetas": {"type": "array", "items": {"type": "string"}},
            "fecha_creacion": {"type": "string", "format": "date-time"}}},
    "SolicitudDocumento": {
        "type": "object", "required": ["tipo", "contenido"],
        "properties": {
            "tipo": {"type": "string", "enum": ["EVIDENCIA_CONSENTIMIENTO",
                                               "AVISO_PRIVACIDAD",
                                               "REPORTE_ORGANIZACIONAL"]},
            "seudonimo_id": {"type": "string", "pattern": "^SEUD-[0-9]{5}$"},
            "unidad_organizacional_id": {"type": "string"},
            "campania_id": {"type": "string"},
            "etiquetas": {"type": "array", "items": {"type": "string"}},
            "contenido": {"type": "object", "additionalProperties": True}}},
}

FILTROS = PARAMS_PAGINACION + [
    {"name": "tipo", "in": "query", "schema": {"type": "string",
     "enum": ["EVIDENCIA_CONSENTIMIENTO", "AVISO_PRIVACIDAD", "REPORTE_ORGANIZACIONAL"]}},
    {"name": "unidad", "in": "query", "schema": {"type": "string"}},
    {"name": "campania", "in": "query", "schema": {"type": "string"}},
    {"name": "seudonimo", "in": "query", "schema": {"type": "string"}},
    {"name": "etiqueta", "in": "query", "schema": {"type": "string"}},
]

RUTAS = {
    "/api/v1/documentos": {
        "get": {"tags": ["Documentos"], "summary": "Lista documentos con filtros",
                "parameters": FILTROS,
                "responses": dict({"200": {"description": "Pagina de documentos"}},
                                  **RESPUESTAS_ERROR)},
        "post": {"tags": ["Documentos"], "summary": "Inserta un documento",
                 "description": "Rechaza con 422 y codigo CAMPO_PROHIBIDO cualquier "
                                "documento que contenga un identificador directo de "
                                "persona, aunque venga anidado: si empleado_id llegara "
                                "a MongoDB, la seudonimizacion dejaria de existir.",
                 "requestBody": {"required": True, "content": {"application/json": {
                     "schema": {"$ref": "#/components/schemas/SolicitudDocumento"},
                     "example": {"tipo": "EVIDENCIA_CONSENTIMIENTO",
                                 "seudonimo_id": "SEUD-00001",
                                 "campania_id": "CAMP-2026-S1",
                                 "etiquetas": ["consentimiento", "nom035"],
                                 "contenido": {"version_aviso": "AVISO-v1",
                                               "decision": "ACEPTADO",
                                               "canal": "portal web"}}}}},
                 "responses": dict({"201": {"description": "Documento creado"}},
                                   **RESPUESTAS_ERROR)}},

    "/api/v1/documentos/{documento_id}": {
        "get": {"tags": ["Documentos"], "summary": "Recupera un documento",
                "parameters": [{"name": "documento_id", "in": "path", "required": True,
                                "schema": {"type": "string"}}],
                "responses": dict({"200": {"description": "Documento"}},
                                  **RESPUESTAS_ERROR)},
        "put": {"tags": ["Documentos"], "summary": "Actualiza y sube la version",
                "description": "Una EVIDENCIA_CONSENTIMIENTO responde 409 "
                               "DOCUMENTO_INMUTABLE: su valor como prueba depende de "
                               "que nadie la pueda cambiar despues del hecho.",
                "parameters": [{"name": "documento_id", "in": "path", "required": True,
                                "schema": {"type": "string"}}],
                "requestBody": {"required": True, "content": {"application/json": {
                    "schema": {"type": "object", "required": ["contenido"],
                               "properties": {"contenido": {"type": "object"}}}}}},
                "responses": dict({"200": {"description": "Documento actualizado"},
                                   "409": {"description": "Documento inmutable"}},
                                  **RESPUESTAS_ERROR)}},

    "/api/v1/documentos/resumen": {"get": {
        "tags": ["Agregacion"], "summary": "Conteo por tipo y unidad",
        "description": "Agregacion de MongoDB. Cuenta documentos, no respuestas: "
                       "no expone ningun valor de bienestar, de modo que no pasa "
                       "por el mecanismo de privacidad diferencial.",
        "responses": dict({"200": {"description": "Resumen agregado"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/documentos/por-campania/{campania_id}": {"get": {
        "tags": ["Agregacion"],
        "summary": "Recuperacion por identificador relacionado entre las dos bases",
        "description": "Lee la campania en PostgreSQL y sus documentos en MongoDB, "
                       "cruzados por campania_id.",
        "parameters": [{"name": "campania_id", "in": "path", "required": True,
                        "schema": {"type": "string"}}],
        "responses": dict({"200": {"description": "Campania con sus documentos"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/documentos/indices": {"post": {
        "tags": ["Operacion"], "summary": "Declara los indices de MongoDB",
        "description": "Idempotente: se puede invocar en cada despliegue. Los "
                       "indices se declaran en el codigo porque uno creado a mano "
                       "desaparece en el siguiente despliegue.",
        "responses": dict({"200": {"description": "Indices creados"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Documentos", "description": "Insercion, consulta y actualizacion."},
    {"name": "Agregacion", "description": "Agregaciones y cruces con PostgreSQL."},
    {"name": "Operacion", "description": "Indices y mantenimiento."},
]


def montar(app):
    return registrar_openapi(
        app, "documents-service — Bienestar Nexum",
        "Evidencias de consentimiento, avisos versionados y reportes.\n\n"
        "Es el servicio que justifica MongoDB: los tres tipos de documento "
        "tienen estructuras distintas entre si y cambian de version a version. "
        "Forzarlos a columnas fijas produciria muchas columnas nulas o un "
        "modelo entidad-atributo-valor dificil de mantener.\n\n"
        "No guarda nada que identifique a una persona: los documentos se "
        "referencian por seudonimo o por unidad.",
        RUTAS, ESQUEMAS, ETIQUETAS, puerto=8103)
