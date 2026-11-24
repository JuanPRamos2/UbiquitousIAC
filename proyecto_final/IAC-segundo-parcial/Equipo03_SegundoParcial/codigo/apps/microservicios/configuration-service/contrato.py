"""Contrato OpenAPI de configuration-service.

El contrato publica dos cosas que no se ven en la firma de los endpoints:

1. **Que leer los parámetros no exige el permiso de cambiarlos.** Quien ve
   un tablero tiene derecho a saber con qué umbral se publicó. Esconder el
   valor de k no protege a nadie: lo que protege es el umbral y el ruido,
   no el secreto sobre sus valores. Si el contrato no lo dijera, quien lo
   integre pediría PARAMETRO_ADMIN para mostrar una nota al pie.

2. **Que cambiar el umbral NO vuelve a publicar nada.** Es la confusión
   más probable y la más cara: alguien baja k esperando ver las unidades
   suprimidas y nada cambia, porque los agregados ya publicados guardan el
   valor y el ruido que se les aplicó con el k que regía entonces. De ahí
   que el historial sea lo único que permite saber con qué criterio se
   publicó cada campaña.
"""
from comun.openapi import RESPUESTAS_ERROR, registrar_openapi

ESQUEMAS = {
    "Parametro": {
        "type": "object",
        "properties": {
            "clave": {"type": "string", "example": "k_umbral_minimo"},
            "valor": {"type": "number"},
            "unidad": {"type": "string", "nullable": True},
            "descripcion": {"type": "string"},
            "justificacion": {
                "type": "string",
                "description": "Por que el valor es ese. Viaja con el "
                               "parametro porque un umbral sin motivo "
                               "escrito no se puede defender ni discutir."},
            "minimo": {"type": "number", "nullable": True},
            "maximo": {"type": "number", "nullable": True},
            "congelar_en_campania_abierta": {"type": "boolean"},
            "motivo_limite": {"type": "string", "nullable": True},
            "modificable": {
                "type": "boolean",
                "description": "Si se puede cambiar AHORA MISMO. Se calcula "
                               "aqui a proposito: un cliente que tuviera "
                               "que deducirlo cruzando la lista de "
                               "campanias abiertas con una columna "
                               "booleana lo deduciria mal."},
            "motivo_no_modificable": {"type": "string", "nullable": True},
        },
    },
    "CambioParametro": {
        "type": "object",
        "description": "Una fila del historial. Trae el valor ANTERIOR: sin "
                       "el no se puede reconstruir con que umbral se "
                       "publico cada campania, que es para lo unico que "
                       "existiria el historial.",
        "properties": {
            "cambio_id": {"type": "integer"},
            "valor_anterior": {"type": "number", "nullable": True},
            "valor_nuevo": {"type": "number"},
            "justificacion": {"type": "string"},
            "actor_usuario_id": {"type": "string"},
            "campanias_abiertas": {
                "type": "array", "items": {"type": "string"},
                "description": "Que campanias estaban abiertas cuando se "
                               "hizo el cambio. Permite saber si afecto a "
                               "una medicion en curso, y no se puede "
                               "reconstruir despues porque los estados de "
                               "campania cambian."},
            "fecha_cambio": {"type": "string", "format": "date-time"},
        },
    },
}

RUTAS = {
    "/api/v1/configuracion/parametros": {"get": {
        "tags": ["Parametros"],
        "summary": "Los parametros vigentes, con su limite y su motivo",
        "description":
            "NO exige PARAMETRO_ADMIN. Basta cualquier permiso de consulta "
            "de agregados o de bitacora: quien ve un tablero tiene derecho "
            "a saber con que umbral se publico. Esconder el valor de k no "
            "protege a nadie, porque lo que protege es el umbral mismo y el "
            "ruido, no el secreto sobre su valor. Esto es privacidad "
            "diferencial, no seguridad por oscuridad.",
        "responses": dict({"200": {"description": "Parametros vigentes"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/configuracion/parametros/{clave}": {
        "get": {
            "tags": ["Parametros"],
            "summary": "Un parametro con su historial completo",
            "parameters": [{"name": "clave", "in": "path", "required": True,
                            "schema": {"type": "string"}}],
            "responses": dict({"200": {"description": "Parametro e historial"}},
                              **RESPUESTAS_ERROR)},
        "patch": {
            "tags": ["Parametros"],
            "summary": "Cambia un parametro, con justificacion y historial",
            "description":
                "Permiso: PARAMETRO_ADMIN.\n\n"
                "El servicio no hace el UPDATE: llama a "
                "`configuracion.fn_cambiar_parametro`, que es SECURITY "
                "DEFINER y escribe el historial en la MISMA transaccion. El "
                "rol de la aplicacion no tiene UPDATE sobre "
                "`agregado.parametro_privacidad`, asi que no existe un "
                "segundo camino: un historial que se puede evitar no es un "
                "historial.\n\n"
                "Tres rechazos, cada uno con su codigo porque cada uno se "
                "arregla distinto:\n\n"
                "  · **422 FUERA_DE_LIMITE** — el valor sale del rango "
                "declarado en `configuracion.limite_parametro`. El piso del "
                "umbral k esta en la BASE y no en este servicio: una "
                "validacion en Python la salta cualquiera con acceso a "
                "psql, y la afirmacion central del proyecto no puede "
                "depender de que nadie lo haga.\n\n"
                "  · **409 CAMPANIA_ABIERTA** — hay parametros congelados "
                "mientras una campania este abierta. Cambiar el umbral a "
                "mitad de una medicion produce un tablero donde unas "
                "unidades se publicaron con un criterio y otras con otro, "
                "sin que nada en la pantalla lo diga.\n\n"
                "  · **422 VALIDACION** — la justificacion no llega a 30 "
                "caracteres.\n\n"
                "**El cambio NO vuelve a publicar nada.** Los agregados ya "
                "publicados guardan el valor y el ruido que se les aplico "
                "con el k que regia entonces: bajar el umbral ahora no "
                "republica un grupo que se suprimio antes.",
            "parameters": [{"name": "clave", "in": "path", "required": True,
                            "schema": {"type": "string"}}],
            "requestBody": {"required": True, "content": {"application/json": {
                "schema": {"type": "object",
                           "required": ["valor", "justificacion"],
                           "properties": {
                               "valor": {"type": "number"},
                               "justificacion": {"type": "string",
                                                 "minLength": 30}}}}}},
            "responses": dict({
                "200": {"description": "Cambiado, con el valor anterior"},
                "409": {"description": "CAMPANIA_ABIERTA"},
                "422": {"description": "FUERA_DE_LIMITE o VALIDACION"}},
                **RESPUESTAS_ERROR)}},

    "/api/v1/configuracion/limites-perfil": {"get": {
        "tags": ["Limites"],
        "summary": "Los topes de consulta por perfil, con su motivo",
        "description":
            "Existen porque los topes estaban escritos como constantes "
            "dentro de cada servicio. Con eso, un auditor que revisa mil "
            "registros y un colaborador que mira su propia participacion "
            "tenian el mismo tope, y el unico modo de cambiarlo era volver "
            "a desplegar.",
        "responses": dict({"200": {"description": "Topes por perfil"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/configuracion/mis-limites": {"get": {
        "tags": ["Limites"],
        "summary": "Los topes que aplican a quien pregunta",
        "description":
            "Pide token pero ningun permiso en particular. Saber cuantas "
            "consultas te quedan no revela nada de nadie, y un cliente que "
            "no lo sabe reintenta en bucle contra un 429, que es justo lo "
            "que el limite venia a evitar.",
        "responses": dict({"200": {"description": "Topes del perfil propio"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Parametros",
     "description": "Umbral k, presupuestos de epsilon y tolerancias, con "
                    "su historial."},
    {"name": "Limites",
     "description": "Topes de consulta por perfil."},
]


def montar(app):
    return registrar_openapi(
        app, "configuration-service — Bienestar Nexum",
        "Gobierno de los parametros del sistema.\n\n"
        "QUE PROBLEMA RESUELVE. El umbral k y los presupuestos de epsilon "
        "viven en `agregado.parametro_privacidad` desde el esquema base, "
        "pero no habia camino para cambiarlos: se cambiaban con un UPDATE "
        "suelto, y un UPDATE pisa el valor anterior. El umbral k es la "
        "afirmacion central del proyecto y se podia bajar de 5 a 2 sin "
        "justificacion y sin que quedara constancia.\n\n"
        "Ahora el unico camino pasa por aqui, y por aqui siempre queda "
        "historial con el valor viejo, el motivo y las campanias que "
        "estaban abiertas.",
        rutas=RUTAS, esquemas=ESQUEMAS, etiquetas=ETIQUETAS)
