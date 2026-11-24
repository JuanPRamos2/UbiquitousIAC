"""Contrato OpenAPI de auth-service."""
from comun.openapi import PARAMS_PAGINACION, RESPUESTAS_ERROR, registrar_openapi

ESQUEMAS = {
    "SolicitudLogin": {
        "type": "object", "required": ["correo", "contrasena"],
        "properties": {
            "correo": {"type": "string", "format": "email",
                       "example": "mariana.solis@nexum.com.mx"},
            "contrasena": {"type": "string", "format": "password",
                           "minLength": 1, "example": "demo123"}}},
    "SolicitudRenovar": {
        "type": "object", "required": ["token_renovacion"],
        "properties": {"token_renovacion": {
            "type": "string",
            "description": "Token de renovacion recibido al iniciar sesion. "
                           "Un token de ACCESO aqui se rechaza: si sirviera, "
                           "robarlo permitiria extender la sesion sin limite."}}},
    "Sesion": {
        "type": "object",
        "properties": {
            "token_acceso": {"type": "string",
                             "description": "Vigencia corta (15 minutos)."},
            "token_renovacion": {"type": "string",
                                 "description": "Vigencia larga (7 dias). Al usarse "
                                                "se rota: la sesion anterior queda "
                                                "revocada."},
            "tipo_token": {"type": "string", "enum": ["Bearer"]},
            "expira_en": {"type": "integer", "example": 900},
            "emitido_en": {"type": "string", "format": "date-time"},
            "usuario": {"type": "object", "properties": {
                "usuario_id": {"type": "string", "example": "USR-00003"},
                "nombre": {"type": "string", "example": "Mariana Solis"},
                "correo": {"type": "string", "format": "email"},
                "perfil": {"type": "string", "example": "Especialista de bienestar"},
                "perfil_id": {"type": "integer", "example": 3},
                "unidad_alcance": {"type": "string", "nullable": True,
                                   "description": "null significa toda la organizacion."}}}}},
    "Validacion": {
        "type": "object",
        "properties": {
            "valido": {"type": "boolean"},
            "usuario_id": {"type": "string"}, "perfil": {"type": "string"},
            "perfil_id": {"type": "integer"},
            "unidad_alcance": {"type": "string", "nullable": True},
            "jti": {"type": "string"}, "expira": {"type": "integer"}}},
}


def _exito(ref, descripcion, ejemplo_xml):
    return {"description": descripcion, "content": {
        "application/json": {"schema": {"$ref": f"#/components/schemas/{ref}"}},
        "application/xml": {"schema": {"$ref": f"#/components/schemas/{ref}"},
                            "example": ejemplo_xml}}}


RUTAS = {
    "/api/v1/auth/login": {"post": {
        "tags": ["Sesion"], "summary": "Inicia sesion y emite los dos tokens",
        "description": (
            "Devuelve un token de acceso de vigencia corta y uno de renovacion "
            "de vigencia larga.\n\n"
            "El mensaje de error NO distingue entre correo inexistente y "
            "contrasena incorrecta: distinguirlos permitiria averiguar que "
            "correos existen en la organizacion.\n\n"
            "Tras cinco intentos fallidos la cuenta queda bloqueada 15 minutos."),
        "security": [],
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/SolicitudLogin"}}}},
        "responses": dict({"200": _exito(
            "Sesion", "Sesion iniciada",
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<sesion xmlns="http://nexum.com.mx/bienestar/v1">\n'
            '  <token_acceso>eyJhbGciOiJIUzI1NiJ9...</token_acceso>\n'
            '  <tipo_token>Bearer</tipo_token>\n'
            '  <expira_en>900</expira_en>\n'
            '</sesion>')}, **RESPUESTAS_ERROR)}},

    "/api/v1/auth/renovar": {"post": {
        "tags": ["Sesion"], "summary": "Renueva la sesion rotando el token",
        "description": (
            "Emite una sesion nueva y revoca la anterior. La rotacion es "
            "deliberada: si alguien robo el token de renovacion, su uso deja "
            "rastro y solo uno de los dos conserva la sesion."),
        "security": [],
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/SolicitudRenovar"}}}},
        "responses": dict({"200": _exito("Sesion", "Sesion renovada", "")},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/auth/logout": {"post": {
        "tags": ["Sesion"], "summary": "Cierra la sesion y la revoca en todos los componentes",
        "description": (
            "Agrega el identificador del token a la lista de revocados en Redis "
            "y borra la sesion. Como el sistema web y los microservicios "
            "comparten esa lista, el cierre surte efecto de inmediato en todos."),
        "responses": dict({"200": {"description": "Sesion revocada"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/auth/validar": {"get": {
        "tags": ["Sesion"], "summary": "Comprueba si el token sigue sirviendo",
        "description": "Verifica firma, vigencia y que la sesion siga viva en Redis.",
        "responses": dict({"200": _exito("Validacion", "Token valido", "")},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/auth/permisos": {"get": {
        "tags": ["Sesion"], "summary": "Permisos vigentes del perfil",
        "description": (
            "Los permisos NO viajan dentro del token a proposito: si viajaran, "
            "quitarle un permiso a un perfil no surtiria efecto hasta que "
            "caducaran todos los tokens ya emitidos."),
        "responses": dict({"200": {"description": "Lista de codigos de permiso"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [{"name": "Sesion",
              "description": "Emision, renovacion, validacion y revocacion de tokens."}]


def montar(app):
    return registrar_openapi(
        app, "auth-service — Bienestar Nexum",
        "Autenticacion y ciclo de vida de la sesion.\n\n"
        "Responsabilidad unica: emitir, renovar, validar y revocar tokens. "
        "No conoce el negocio. Todo microservicio valida el JWT con la "
        "libreria comun y consulta Redis, sin llamar a este servicio en "
        "cada peticion.",
        RUTAS, ESQUEMAS, ETIQUETAS, puerto=8101)
