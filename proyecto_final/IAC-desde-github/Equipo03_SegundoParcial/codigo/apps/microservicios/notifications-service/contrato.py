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

    "/api/v1/notificaciones/preferencias": {
        "get": {
            "tags": ["Notificaciones"],
            "summary": "Preferencias del usuario que llama",
            "description":
                "Siempre responde completas: un usuario que nunca guardo "
                "nada recibe los valores por omision en lugar de un 404.\n\n"
                "El push viene APAGADO por omision. Si viniera encendido, la "
                "primera notificacion llegaria a la pantalla bloqueada de "
                "alguien que nunca eligio eso.",
            "responses": dict({"200": {"description": "Preferencias"}},
                              **RESPUESTAS_ERROR)},
        "put": {
            "tags": ["Notificaciones"],
            "summary": "Guarda las preferencias del usuario que llama",
            "description":
                "El usuario sale del TOKEN, nunca del cuerpo: si saliera del "
                "cuerpo, cualquiera podria apagarle las notificaciones a otra "
                "persona.\n\n"
                "Un campo desconocido se rechaza en lugar de ignorarse: quien "
                "manda 'notificaciones' en vez de 'bandeja' cree que guardo "
                "algo y no guardo nada.\n\n"
                "Hay tipos que el usuario NO puede silenciarse "
                "(CONSENTIMIENTO_POR_VENCER): es una obligacion del programa "
                "hacia la persona, no una cortesia.",
            "requestBody": {"required": True, "content": {"application/json": {
                "schema": {"type": "object", "properties": {
                    "bandeja": {"type": "boolean"},
                    "push": {"type": "boolean"},
                    "tipos_silenciados": {"type": "array",
                                          "items": {"type": "string"}},
                    "silencio_desde": {"type": "integer", "minimum": 0,
                                       "maximum": 23},
                    "silencio_hasta": {"type": "integer", "minimum": 0,
                                       "maximum": 23}}}}}},
            "responses": dict({"200": {"description": "Preferencias guardadas"}},
                              **RESPUESTAS_ERROR)}},

    "/api/v1/notificaciones/dispositivos": {
        "post": {
            "tags": ["Notificaciones"],
            "summary": "Registra el token de push de un aparato",
            "description":
                "Se guarda por (usuario, token) y no solo por usuario: una "
                "persona puede tener el telefono y la tableta, y guardar solo "
                "el ultimo dejaria al otro aparato sin avisos sin que nadie "
                "lo note.",
            "requestBody": {"required": True, "content": {"application/json": {
                "schema": {"type": "object", "required": ["token", "plataforma"],
                           "properties": {
                               "token": {"type": "string"},
                               "plataforma": {"type": "string",
                                              "enum": ["ANDROID", "IOS",
                                                       "ESCRITORIO"]}}}}}},
            "responses": dict({"201": {"description": "Registrado"}},
                              **RESPUESTAS_ERROR)},
        "delete": {
            "tags": ["Notificaciones"],
            "summary": "Da de baja un token al cerrar sesion",
            "description":
                "Sin esto, un telefono del que alguien cerro sesion seguiria "
                "recibiendo avisos de una cuenta que ya no esta abierta ahi.",
            "responses": dict({"200": {"description": "Dado de baja"}},
                              **RESPUESTAS_ERROR)}},

    "/api/v1/notificaciones/push/pendientes": {"get": {
        "tags": ["Operacion"],
        "summary": "Cola de push que el repartidor tiene que entregar",
        "description":
            "Este servicio NO habla con Firebase ni con APNs: decide quien "
            "debe recibir un push y lo deja en esta cola. La entrega la hace "
            "un repartidor aparte, que es el unico componente que necesita "
            "las credenciales del proveedor.\n\n"
            "No es una tarea pendiente, es una separacion a proposito: meter "
            "esas credenciales en el servicio que ademas lee la base de "
            "notificaciones significa que cualquier fallo aqui las expone.\n\n"
            "El cuerpo del push es DELIBERADAMENTE generico. Se dibuja en la "
            "pantalla bloqueada, donde lo ve cualquiera que este cerca: un "
            "push que dijera 'te falta responder la encuesta de Call Center "
            "Turno B' revelaria donde trabaja esa persona y que esta en un "
            "programa de bienestar.",
        "responses": dict({"200": {"description": "Pendientes"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/notificaciones/push/{push_id}": {"put": {
        "tags": ["Operacion"],
        "summary": "El repartidor informa como le fue",
        "description":
            "Un envio FALLIDO no se borra: se le suma un intento y se deja "
            "pendiente. TOKEN_INVALIDO si lo borra y da de baja el aparato. "
            "Esa distincion separa 'reintentar' de 'este telefono se "
            "desinstalo'; sin ella, la cola reintentaria para siempre contra "
            "aparatos que ya no estan.",
        "parameters": [{"name": "push_id", "in": "path", "required": True,
                        "schema": {"type": "string"}}],
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"type": "object", "required": ["estado"],
                       "properties": {
                           "estado": {"type": "string",
                                      "enum": ["ENTREGADO", "FALLIDO",
                                               "TOKEN_INVALIDO"]},
                           "error": {"type": "string"}}}}}},
        "responses": dict({"200": {"description": "Actualizado"}},
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
        RUTAS, ESQUEMAS, ETIQUETAS, puerto=8106)
