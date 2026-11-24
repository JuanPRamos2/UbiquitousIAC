"""Contrato OpenAPI de sync-service.

El contrato publica la cosa que un cliente NO puede adivinar y de la que
depende que la sincronización funcione: **quién genera el identificador de
idempotencia, y qué estados se reenvían y cuáles no**.

Las dos aplicaciones cliente —la de escritorio y la móvil— implementan el
reintento por separado. Una regla que viva solo en el servidor se
implementa distinto en cada una, y la diferencia solo se ve cuando falla
la red, que es cuando no hay nadie mirando. Por eso
`/contrato-de-reintento` es un endpoint y no un comentario.
"""
from comun.openapi import RESPUESTAS_ERROR, registrar_openapi

ESQUEMAS = {
    "OperacionEntrante": {
        "type": "object",
        "description": "Una operacion capturada por el cliente, quizas sin "
                       "red. Va por SEUDONIMO: un empleado_id, correo o "
                       "nombre aqui se RECHAZA, no se ignora.",
        "required": ["operacion_cliente_id", "seudonimo_id", "campania_id",
                     "valores"],
        "properties": {
            "operacion_cliente_id": {
                "type": "string", "maxLength": 80,
                "description": "Lo genera el CLIENTE antes del primer "
                               "intento y lo repite identico en cada "
                               "reenvio. Es lo unico que permite distinguir "
                               "«lo mismo otra vez» de «otro que contesto "
                               "igual»: comparar por contenido descartaria "
                               "como duplicada la respuesta legitima de dos "
                               "personas del mismo turno que contestaron "
                               "parecido.",
                "example": "mov-9f3a1c-0007"},
            "tipo": {"type": "string", "enum": ["AUTOREPORTE"],
                     "default": "AUTOREPORTE"},
            "seudonimo_id": {"type": "string", "example": "SD-0007"},
            "campania_id": {"type": "string", "example": "CAMP-2026-S4"},
            "valores": {
                "type": "object",
                "description": "Reactivo a valor, como lo espera "
                               "autoreporte.fn_registrar_autoreporte.",
                "additionalProperties": {"type": "integer"},
                "example": {"R-01": 4, "R-02": 3}},
        },
    },
    "ResultadoOperacion": {
        "type": "object",
        "description": "El resultado de UN renglon. El lote no es todo o "
                       "nada: un renglon mal formado no puede perder los "
                       "demas, porque el cliente que los capturo sin red no "
                       "tiene como recuperarlos.",
        "properties": {
            "renglon": {"type": "integer"},
            "operacion_cliente_id": {"type": "string"},
            "estado": {
                "type": "string",
                "enum": ["APLICADA", "DUPLICADA", "EN_CONFLICTO",
                         "RECHAZADA", "ERROR_TEMPORAL"],
                "description":
                    "APLICADA: se registro.\n"
                    "DUPLICADA: ya estaba; se devolvio el resultado "
                    "guardado sin aplicar otra vez.\n"
                    "EN_CONFLICTO: choco con un dato que ya existia y que "
                    "NO se sobrescribe.\n"
                    "RECHAZADA: no paso una validacion o una regla.\n"
                    "ERROR_TEMPORAL: no se pudo aplicar y no se puede "
                    "afirmar que no se haya aplicado."},
            "estado_base": {
                "type": "string",
                "description": "El estado que devolvio "
                               "autoreporte.fn_registrar_autoreporte, sin "
                               "traducir. Se expone para que un problema se "
                               "pueda rastrear hasta la regla que lo causo."},
            "mensaje": {"type": "string"},
            "reintentable": {
                "type": "boolean",
                "description": "Si el cliente DEBE volver a intentarlo. Un "
                               "rechazo por datos mal formados es false "
                               "—volveria a fallar igual— y una campania "
                               "aun no abierta es true, porque una campania "
                               "programada abre despues."},
            "intentos": {"type": "integer"},
            "advertencia": {
                "type": "string",
                "description": "Presente cuando el mismo "
                               "operacion_cliente_id llego con OTRO "
                               "contenido. No se aplico el contenido nuevo: "
                               "describe un cliente que reusa "
                               "identificadores."},
        },
    },
}

RUTAS = {
    "/api/v1/sincronizacion/lotes": {"post": {
        "tags": ["Sincronizacion"],
        "summary": "Recibe un lote de operaciones, idempotente por renglon",
        "description":
            "Acepta JSON y XML, porque la aplicacion de escritorio del "
            "proyecto consume XML exclusivamente.\n\n"
            "**Responde 200 y no 201 a proposito.** El resultado normal de "
            "un lote es parcial —unas aplicadas, unas en conflicto, unas "
            "rechazadas— y 201 «creado» describiria mal algo que puede no "
            "haber creado nada.\n\n"
            "**Reenviar el lote completo es inofensivo.** Si el "
            "`lote_cliente_id` ya se recibio, no se aplica nada otra vez: "
            "se devuelve el MISMO resultado de la primera vez, con "
            "`reenvio: true`. Devolver una respuesta distinta obligaria al "
            "cliente a decidir que hacer con la diferencia, que es el "
            "problema que esto viene a resolver.\n\n"
            "**Los conflictos no se resuelven sobrescribiendo.** Si la "
            "campania ya tiene respuesta de ese seudonimo, se conserva la "
            "primera. Ultimo-que-escribe-gana cambiaria un dato que quizas "
            "ya entro en un agregado publicado: un numero que ya salio, "
            "modificado hacia atras y sin rastro.\n\n"
            "Permiso: AUTOREPORTE_RESPONDER. Es el permiso de la persona "
            "que contesta, no uno de servicio: la aplicacion se autentica "
            "como quien captura.",
        "requestBody": {"required": True, "content": {
            "application/json": {"schema": {
                "type": "object",
                "required": ["lote_cliente_id", "origen", "operaciones"],
                "properties": {
                    "lote_cliente_id": {
                        "type": "string", "maxLength": 80,
                        "description": "Identificador del lote generado por "
                                       "el cliente. Es lo que permite "
                                       "reenviar el lote completo sin "
                                       "duplicar nada."},
                    "origen": {"type": "string",
                               "enum": ["ESCRITORIO", "MOVIL", "WEB", "OTRO"]},
                    "operaciones": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/OperacionEntrante"}}}}},
            "application/xml": {"schema": {
                "type": "object",
                "description": "Mismo contenido. El serializador del "
                               "proyecto envuelve en plural y nombra en "
                               "singular: <operaciones><operacion>…"}}}},
        "responses": dict(
            {"200": {"description": "Resultado renglon por renglon, con la "
                                    "lista de lo que SI hay que reenviar"}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/sincronizacion/lotes/{lote_cliente_id}": {"get": {
        "tags": ["Sincronizacion"],
        "summary": "Que paso con un lote, buscado por la clave del cliente",
        "description":
            "Por la clave del CLIENTE y no por el identificador interno a "
            "proposito: si el cliente perdio la respuesta, el identificador "
            "interno es justamente lo que no tiene.\n\n"
            "Un 404 aqui es informacion util y no un error: significa que "
            "el lote no llego, asi que se puede reenviar tal cual.",
        "parameters": [{"name": "lote_cliente_id", "in": "path",
                        "required": True, "schema": {"type": "string"}}],
        "responses": dict({"200": {"description": "El lote con su detalle"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/sincronizacion/contrato-de-reintento": {"get": {
        "tags": ["Sincronizacion"],
        "summary": "Las reglas de reenvio, para que el cliente no las adivine",
        "description":
            "Publica quien genera el identificador de idempotencia, que "
            "estados se reenvian y cuales no, el tope por lote y la espera "
            "recomendada.\n\n"
            "Esta aqui porque las dos aplicaciones cliente implementan el "
            "reintento por separado: una regla que viva solo en el servidor "
            "se implementa distinto en cada una, y la diferencia solo se ve "
            "cuando falla la red, que es cuando no hay nadie mirando.",
        "responses": dict({"200": {"description": "Las reglas de reenvio"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/sincronizacion/clientes-insistentes": {"get": {
        "tags": ["Operacion"],
        "summary": "Operaciones con muchos intentos: describen un cliente roto",
        "description":
            "Un cliente que reenvia mil veces algo ya resuelto no rompe "
            "nada —la idempotencia lo absorbe— y por eso no se nota. Esta "
            "es la unica forma de verlo antes de que sea un problema de "
            "carga.\n\n"
            "Permiso: BITACORA_CONSULTAR o PARAMETRO_ADMIN.",
        "responses": dict({"200": {"description": "Operaciones insistentes"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Sincronizacion",
     "description": "Entrega de operaciones capturadas sin red."},
    {"name": "Operacion",
     "description": "Vigilancia del comportamiento de los clientes."},
]


def montar(app):
    return registrar_openapi(
        app, "sync-service — Bienestar Nexum",
        "Sincronizacion de operaciones capturadas por las aplicaciones "
        "cliente donde la red va y viene.\n\n"
        "El problema que resuelve no es «recibir datos»: es que un cliente "
        "sin respuesta NO PUEDE distinguir «no llego» de «llego y se "
        "aplico, y la respuesta se perdio al volver». En el primer caso hay "
        "que reenviar y en el segundo reenviar duplica, asi que un cliente "
        "razonable reenvia siempre. El trabajo de este servicio es hacer "
        "que reenviar sea inofensivo.\n\n"
        "No guarda respuestas. Las respuestas entran por "
        "`autoreporte.fn_registrar_autoreporte`, que es la unica via y la "
        "que aplica las reglas de negocio. Reimplementarlas aqui habria "
        "creado un segundo camino de entrada que podria divergir del "
        "primero, y el dia que divergiera los agregados se contaminarian "
        "sin que nada fallara.",
        rutas=RUTAS, esquemas=ESQUEMAS, etiquetas=ETIQUETAS)
