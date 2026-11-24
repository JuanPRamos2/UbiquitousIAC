"""Contrato OpenAPI de users-service."""
from comun.openapi import PARAMS_PAGINACION, RESPUESTAS_ERROR, registrar_openapi

ESQUEMAS = {
    "Usuario": {
        "type": "object",
        "properties": {
            "usuario_id": {"type": "string", "pattern": "^USR-[0-9]{5}$",
                           "example": "USR-00003"},
            "nombre": {"type": "string", "example": "Mariana"},
            "apellido_paterno": {"type": "string", "example": "Solis"},
            "apellido_materno": {"type": "string", "nullable": True},
            "correo": {"type": "string", "format": "email"},
            "activo": {"type": "boolean"},
            "fecha_ultimo_acceso": {"type": "string", "format": "date-time",
                                    "nullable": True},
            "perfil_id": {"type": "integer", "nullable": True, "example": 3},
            "perfil": {"type": "string", "nullable": True},
            "unidad_alcance_id": {"type": "string", "nullable": True,
                                  "description": "null = alcance en toda la organizacion."}}},
    "SolicitudAlta": {
        "type": "object",
        "required": ["usuario_id", "correo", "nombre", "apellido_paterno",
                     "contrasena", "perfil_id"],
        "properties": {
            "usuario_id": {"type": "string", "pattern": "^USR-[0-9]{5}$"},
            "correo": {"type": "string", "format": "email"},
            "nombre": {"type": "string", "minLength": 2},
            "apellido_paterno": {"type": "string", "minLength": 2},
            "apellido_materno": {"type": "string"},
            "contrasena": {"type": "string", "format": "password", "minLength": 8,
                           "description": "Se cifra con crypt() en la base; el texto "
                                          "plano no se guarda en ningun momento."},
            "perfil_id": {"type": "integer", "example": 1},
            "unidad_alcance_id": {"type": "string", "nullable": True}}},
    "ListaUsuarios": {
        "type": "object",
        "properties": {
            "usuarios": {"type": "array",
                         "items": {"$ref": "#/components/schemas/Usuario"}},
            "paginacion": {"$ref": "#/components/schemas/Paginacion"}}},
}

FILTROS = PARAMS_PAGINACION + [
    {"name": "busqueda", "in": "query", "required": False,
     "schema": {"type": "string"},
     "description": "Busca en nombre, apellido, correo e identificador."},
    {"name": "perfil_id", "in": "query", "required": False,
     "schema": {"type": "integer"}},
    {"name": "activo", "in": "query", "required": False,
     "schema": {"type": "string", "enum": ["true", "false"]}},
]

RUTAS = {
    "/api/v1/usuarios": {
        "get": {"tags": ["Usuarios"], "summary": "Lista usuarios con filtros y paginacion",
                "description": "Requiere el permiso USUARIO_ADMIN.",
                "parameters": FILTROS,
                "responses": dict({"200": {"description": "Pagina de usuarios",
                    "content": {"application/json": {"schema":
                        {"$ref": "#/components/schemas/ListaUsuarios"}},
                        "application/xml": {"schema":
                        {"$ref": "#/components/schemas/ListaUsuarios"},
                        "example": '<?xml version="1.0" encoding="UTF-8"?>\n'
                                   '<usuarios_respuesta xmlns="http://nexum.com.mx/bienestar/v1">\n'
                                   '  <usuarios>\n    <usuario>\n'
                                   '      <usuario_id>USR-00003</usuario_id>\n'
                                   '      <perfil>Especialista de bienestar</perfil>\n'
                                   '      <unidad_alcance_id xsi:nil="true"/>\n'
                                   '    </usuario>\n  </usuarios>\n'
                                   '  <paginacion><pagina>1</pagina></paginacion>\n'
                                   '</usuarios_respuesta>'}}}}, **RESPUESTAS_ERROR)},
        "post": {"tags": ["Usuarios"], "summary": "Da de alta un usuario y le asigna perfil",
                 "description": "Devuelve TODOS los problemas de validacion de una vez, "
                                "no solo el primero.",
                 "requestBody": {"required": True, "content": {"application/json": {
                     "schema": {"$ref": "#/components/schemas/SolicitudAlta"}}}},
                 "responses": dict({"201": {"description": "Usuario creado"},
                                    "409": {"description": "Identificador o correo duplicado"}},
                                   **RESPUESTAS_ERROR)}},

    "/api/v1/usuarios/{usuario_id}": {"get": {
        "tags": ["Usuarios"], "summary": "Detalle de un usuario con sus permisos",
        "parameters": [{"name": "usuario_id", "in": "path", "required": True,
                        "schema": {"type": "string", "pattern": "^USR-[0-9]{5}$"}}],
        "responses": dict({"200": {"description": "Usuario con permisos del perfil"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/usuarios/{usuario_id}/perfil": {"put": {
        "tags": ["Usuarios"], "summary": "Cambia el perfil y el alcance",
        "description": "Revoca las sesiones activas del usuario, para que el cambio "
                       "surta efecto de inmediato y no cuando caduque su token.",
        "parameters": [{"name": "usuario_id", "in": "path", "required": True,
                        "schema": {"type": "string"}}],
        "requestBody": {"required": True, "content": {"application/json": {"schema": {
            "type": "object", "required": ["perfil_id"],
            "properties": {"perfil_id": {"type": "integer"},
                           "unidad_alcance_id": {"type": "string", "nullable": True}}}}}},
        "responses": dict({"200": {"description": "Perfil actualizado"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/usuarios/{usuario_id}/estado": {"put": {
        "tags": ["Usuarios"], "summary": "Activa o desactiva un usuario",
        "description": "Un administrador no puede desactivar su propia cuenta: "
                       "hacerlo podria dejar al sistema sin administradores operativos.",
        "parameters": [{"name": "usuario_id", "in": "path", "required": True,
                        "schema": {"type": "string"}}],
        "requestBody": {"required": True, "content": {"application/json": {"schema": {
            "type": "object", "required": ["activo"],
            "properties": {"activo": {"type": "boolean"}}}}}},
        "responses": dict({"200": {"description": "Estado actualizado"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/perfiles": {"get": {
        "tags": ["Perfiles"], "summary": "Catalogo de perfiles",
        "responses": dict({"200": {"description": "Perfiles con su conteo de permisos"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/perfiles/{perfil_id}/permisos": {"get": {
        "tags": ["Perfiles"], "summary": "Permisos de un perfil",
        "parameters": [{"name": "perfil_id", "in": "path", "required": True,
                        "schema": {"type": "integer"}}],
        "responses": dict({"200": {"description": "Lista de permisos"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Usuarios", "description": "Alta, consulta y cambio de perfil o estado."},
    {"name": "Perfiles", "description": "Catalogo de perfiles y sus permisos."},
]


def montar(app):
    return registrar_openapi(
        app, "users-service — Bienestar Nexum",
        "Administracion de usuarios, perfiles y permisos.\n\n"
        "Una regla atraviesa este servicio: administrar usuarios NO da acceso "
        "al contenido de las respuestas. El rol de base de datos con el que se "
        "conecta carece de permiso de lectura sobre el esquema de autorreporte, "
        "de modo que la separacion no depende de que este codigo se porte bien.",
        RUTAS, ESQUEMAS, ETIQUETAS, puerto=8102)
