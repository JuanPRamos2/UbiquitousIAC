"""Contrato OpenAPI de notifications-service."""
from comun.openapi import PARAMS_PAGINACION, RESPUESTAS_ERROR, registrar_openapi

TIPOS = ["CAMPANIA_ABIERTA", "RECORDATORIO_ENCUESTA", "CONDICION_DETECTADA",
         "PLAN_APROBADO", "CONSENTIMIENTO_POR_VENCER"]

ESQUEMAS = {
    "Notificacion": {
        "type": "object",
        "properties": {
            "notificacion_id": {"type": "string", "pattern": "^NTF-[0-9A-F]{12}$"},
            "lote_id": {"type": "string"},
            "tipo": {"type": "string", "enum": TIPOS},
            "titulo": {"type": "string"},
            "mensaje": {"type": "string"},
            "unidad_organizacional_id": {"type": "string", "nullable": True},
            "campania_id": {"type": "string", "nullable": True},
            "destinatario_usuario_id": {"type": "string", "pattern": "^USR-[0-9]{5}$"},
            "leida": {"type": "boolean"},
            "fecha_lectura": {"type": "string", "format": "date-time", "nullable": True},
            "fecha_creacion": {"type": "string", "format": "date-time"},
            "fecha_expiracion": {"type": "string", "format": "date-time",
                                 "description": "Las notificaciones se borran solas a "
                                                "los 90 dias por indice TTL de MongoDB: "
                                                "minimizacion de datos."}}},
    "SolicitudEnvio": {
        "type": "object", "required": ["tipo", "titulo", "mensaje"],
        "description": "Indica 'destinatarios' o 'unidad_organizacional_id'. Si se "
                       "indica la unidad, se resuelven los usuarios con alcance ahi.",
        "properties": {
            "tipo": {"type": "string", "enum": TIPOS},
            "titulo": {"type": "string", "minLength": 5},
            "mensaje": {"type": "string", "minLength": 10,
                        "description": "No puede contener cifras decimales: publicar "
                                       "un valor de bienestar por esta via saltaria "
                                       "el mecanismo de privacidad diferencial y el "
                                       "presupuesto de epsilon."},
            "destinatarios": {"type": "array",
                              "items": {"type": "string", "pattern": "^USR-[0-9]{5}$"}},
            "unidad_organizacional_id": {"type": "string"},
            "campania_id": {"type": "string"}}},
}

RUTAS = {
    "/api/v1/notificaciones": {"post": {
        "tags": ["Envio"], "summary": "Envia una notificacion interna",
        "description": "Rechaza con 422 y codigo CIFRA_NO_PERMITIDA cualquier titulo "
                       "o mensaje que contenga un valor numerico decimal.",
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/SolicitudEnvio"},
            "examples": {
                "a_una_unidad": {"summary": "A toda una unidad",
                    "value": {"tipo": "CONDICION_DETECTADA",
                              "titulo": "Condicion detectada en tu unidad",
                              "mensaje": "El motor de reglas detecto una condicion "
                                         "sostenida. Revisa el panel para el detalle.",
                              "unidad_organizacional_id": "UO-CC-TURNO-B"}},
                "a_personas": {"summary": "A destinatarios concretos",
                    "value": {"tipo": "RECORDATORIO_ENCUESTA",
                              "titulo": "Recordatorio de encuesta",
                              "mensaje": "Te falta responder la campania abierta.",
                              "destinatarios": ["USR-00001"]}},
                "rechazada": {"summary": "Rechazada: lleva una cifra",
                    "value": {"tipo": "CONDICION_DETECTADA",
                              "titulo": "Condicion detectada",
                              "mensaje": "La carga percibida bajo a 2.9 puntos",
                              "unidad_organizacional_id": "UO-CC-TURNO-B"}}}}}},
        "responses": dict({"201": {"description": "Notificaciones enviadas"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/notificaciones/mias": {"get": {
        "tags": ["Bandeja"], "summary": "Bandeja del usuario autenticado",
        "description": "El destinatario sale del token, no de la URL: nadie puede "
                       "leer la bandeja de otra persona.",
        "parameters": PARAMS_PAGINACION + [
            {"name": "solo_sin_leer", "in": "query",
             "schema": {"type": "string", "enum": ["true", "false"]}}],
        "responses": dict({"200": {"description": "Pagina de notificaciones"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/notificaciones/sin-leer": {"get": {
        "tags": ["Bandeja"], "summary": "Contador de no leidas",
        "description": "Se sirve desde Redis cuando esta disponible, para que "
                       "mostrar el contador en cada pantalla no cueste una "
                       "consulta a MongoDB. Si Redis no responde, cae a MongoDB.",
        "responses": dict({"200": {"description": "Contador"}}, **RESPUESTAS_ERROR)}},

    "/api/v1/notificaciones/{notificacion_id}/leida": {"put": {
        "tags": ["Bandeja"], "summary": "Marca una notificacion como leida",
        "description": "El filtro incluye al destinatario: conocer el identificador "
                       "de la notificacion de otro no permite marcarla.",
        "parameters": [{"name": "notificacion_id", "in": "path", "required": True,
                        "schema": {"type": "string"}}],
        "responses": dict({"200": {"description": "Marcada como leida"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/notificaciones/resumen": {"get": {
        "tags": ["Agregacion"], "summary": "Enviadas y leidas por tipo",
        "responses": dict({"200": {"description": "Resumen agregado"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/notificaciones/indices": {"post": {
        "tags": ["Operacion"], "summary": "Declara los indices, incluido el TTL",
        "responses": dict({"200": {"description": "Indices creados"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Envio", "description": "Envio de notificaciones internas."},
    {"name": "Bandeja", "description": "Consulta y lectura por parte del destinatario."},
    {"name": "Agregacion", "description": "Resumen de envio y lectura."},
    {"name": "Operacion", "description": "Indices y mantenimiento."},
]


def montar(app):
    return registrar_openapi(
        app, "notifications-service — Bienestar Nexum",
        "Notificaciones internas: campania abierta, recordatorio, condicion "
        "detectada y plan aprobado.\n\n"
        "Dos restricciones del dominio que el servicio hace cumplir: una "
        "notificacion nunca contiene un valor de bienestar, y nunca se refiere "
        "a una persona cuando va dirigida a un perfil con autoridad laboral.",
        RUTAS, ESQUEMAS, ETIQUETAS, puerto=8104)
