"""Contrato OpenAPI de interventions-service.

El contrato publica dos cosas que no se ven en la firma de los endpoints y
que son la razón de ser del servicio:

1. **El ciclo de vida completo.** Qué estado puede pasar a cuál. Un proceso
   de aprobación cuyas transiciones no están escritas no se puede auditar:
   cualquier salto parece legítimo después del hecho.

2. **Lo que el modelo no admite.** Ninguna operación acepta un empleado ni
   un seudónimo como objetivo, porque `intervencion.plan` no tiene dónde
   guardarlo. La garantía G1 del proyecto lo comprueba contra el catálogo
   del sistema.
"""
from comun.openapi import RESPUESTAS_ERROR, registrar_openapi

ESQUEMAS = {
    "PlanIntervencion": {
        "type": "object",
        "description": "Una accion sobre una UNIDAD organizacional. Nunca "
                       "sobre una persona: el modelo de datos no tiene donde "
                       "guardar un objetivo individual.",
        "properties": {
            "intervencion_id": {"type": "integer"},
            "unidad_organizacional_id": {"type": "string",
                                         "example": "UO-CC-TURNO-B"},
            "unidad": {"type": "string"},
            "tipo_intervencion": {"type": "string",
                                  "example": "REDISTRIBUCION_CARGA"},
            "estado": {
                "type": "string",
                "enum": ["PROPUESTA", "APROBADA", "EN_EJECUCION",
                         "FINALIZADA", "CANCELADA"]},
            "justificacion": {
                "type": "string",
                "description": "Obligatoria, minimo 20 caracteres. Intervenir "
                               "sobre un equipo sin dejar dicho por que es lo "
                               "que convierte un programa de bienestar en una "
                               "herramienta de presion."},
            "resultado_esperado": {
                "type": "string",
                "description": "Obligatorio: sin el no hay nada contra que "
                               "evaluar despues."},
            "fecha_inicio": {"type": "string", "format": "date",
                             "nullable": True},
            "fecha_fin": {"type": "string", "format": "date", "nullable": True},
            "responsable_usuario_id": {"type": "string", "nullable": True},
            "campania_linea_base": {"type": "string", "nullable": True},
        },
    },
    "Evaluacion": {
        "type": "object",
        "description": "Comparacion entre dos campanias sobre valores YA "
                       "PUBLICADOS. No consume presupuesto de epsilon.",
        "properties": {
            "campania_antes": {"type": "string"},
            "campania_despues": {"type": "string"},
            "valor_antes": {"type": "number", "format": "double",
                            "nullable": True},
            "valor_despues": {"type": "number", "format": "double",
                              "nullable": True},
            "variacion": {"type": "number", "format": "double",
                          "nullable": True},
            "conclusion": {
                "type": "string",
                "enum": ["MEJORA", "DETERIORO", "SIN_CAMBIO",
                         "SIN_DATOS_SUFICIENTES"],
                "description": "Las tres primeras se guardan; "
                               "SIN_DATOS_SUFICIENTES no, porque no es una "
                               "conclusion sino la ausencia de una.\n\n"
                               "SIN_DATOS_SUFICIENTES cuando el valor de "
                               "antes o el de despues vino suprimido. NO se "
                               "toma como cero: un valor suprimido es "
                               "ausencia de dato, y tratarlo como cero "
                               "produciria una mejora o un empeoramiento "
                               "inventados."},
            "nota_metodologica": {
                "type": "string",
                "description": "Deja dicho que la evaluacion NO atribuye "
                               "causalidad: registra que la unidad se movio "
                               "despues de la intervencion, no que se movio "
                               "POR la intervencion."},
            "epsilon_consumido": {"type": "number", "example": 0.0},
        },
    },
}

RUTAS = {
    "/api/v1/intervenciones/tipos": {"get": {
        "tags": ["Catalogo"],
        "summary": "Tipos de intervencion disponibles, con su ambito",
        "description":
            "El ambito se devuelve a proposito: deja ver que TODOS son "
            "organizacionales. No existe un tipo cuyo ambito sea una "
            "persona, y la ausencia es la garantia.",
        "responses": dict({"200": {"description": "Catalogo de tipos"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/intervenciones": {
        "get": {
            "tags": ["Planes"],
            "summary": "Lista los planes del alcance del perfil",
            "description":
                "El alcance sale del perfil asignado y nunca del parametro: "
                "si saliera del parametro, bastaria cambiar la URL para ver "
                "los planes de otra area.",
            "parameters": [
                {"name": "estado", "in": "query", "required": False,
                 "schema": {"type": "string",
                            "enum": ["PROPUESTA", "APROBADA", "EN_EJECUCION",
                                     "FINALIZADA", "CANCELADA"]}},
                {"name": "unidad_organizacional_id", "in": "query",
                 "required": False, "schema": {"type": "string"}},
            ],
            "responses": dict({"200": {"description": "Planes paginados"}},
                              **RESPUESTAS_ERROR)},
        "post": {
            "tags": ["Planes"],
            "summary": "Propone un plan de intervencion",
            "description":
                "Exige justificacion y resultado esperado, los dos con un "
                "minimo de longitud. No se puede crear un plan vacio.\\n\\n"
                "Permiso: INTERVENCION_PROPONER. Proponer NO aprueba: son "
                "permisos distintos, porque quien detecta la necesidad no es "
                "quien autoriza el gasto y el cambio organizacional.",
            "requestBody": {"required": True, "content": {"application/json": {
                "schema": {"type": "object",
                           "required": ["unidad_organizacional_id",
                                        "tipo_intervencion", "justificacion",
                                        "resultado_esperado"],
                           "properties": {
                               "unidad_organizacional_id": {"type": "string"},
                               "tipo_intervencion": {"type": "string"},
                               "justificacion": {"type": "string",
                                                 "minLength": 20},
                               "resultado_esperado": {"type": "string",
                                                      "minLength": 20},
                               "deteccion_id": {"type": "integer"},
                               "fecha_inicio": {"type": "string",
                                                "format": "date"},
                               "fecha_fin": {"type": "string",
                                             "format": "date"},
                               "responsable_usuario_id": {"type": "string"},
                               "campania_linea_base": {"type": "string"}}}}}},
            "responses": dict({"201": {"description": "Plan propuesto"}},
                              **RESPUESTAS_ERROR)}},

    "/api/v1/intervenciones/{intervencion_id}": {"get": {
        "tags": ["Planes"],
        "summary": "El plan con su seguimiento y sus evaluaciones",
        "description":
            "Incluye `transiciones_posibles`: a que estados se puede pasar "
            "desde el actual. Asi el cliente no tiene que conocer la maquina "
            "de estados ni adivinarla.",
        "parameters": [{"name": "intervencion_id", "in": "path",
                        "required": True, "schema": {"type": "integer"}}],
        "responses": dict({"200": {"description": "Plan con su historial"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/intervenciones/{intervencion_id}/estado": {"patch": {
        "tags": ["Planes"],
        "summary": "Avanza el estado por una transicion declarada",
        "description":
            "Transiciones permitidas:\\n\\n"
            "  PROPUESTA    -> APROBADA | CANCELADA\\n"
            "  APROBADA     -> EN_EJECUCION | CANCELADA\\n"
            "  EN_EJECUCION -> FINALIZADA | CANCELADA\\n"
            "  FINALIZADA   -> (final)\\n"
            "  CANCELADA    -> (final)\\n\\n"
            "Un plan terminado o cancelado NO se reabre. Si hace falta volver "
            "a actuar sobre la unidad es un plan nuevo, con su propia "
            "justificacion y su propia linea base: reabrir el viejo borraria "
            "la historia de lo que ya se intento.\\n\\n"
            "Pasar a APROBADA exige INTERVENCION_APROBAR; el permiso de "
            "seguimiento no alcanza.\\n\\n"
            "Una transicion no declarada responde 409 TRANSICION_INVALIDA y "
            "dice cuales si se pueden desde el estado actual.",
        "parameters": [{"name": "intervencion_id", "in": "path",
                        "required": True, "schema": {"type": "integer"}}],
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"type": "object", "required": ["estado"],
                       "properties": {"estado": {"type": "string"}}}}}},
        "responses": dict({"200": {"description": "Estado actualizado"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/intervenciones/{intervencion_id}/seguimiento": {"post": {
        "tags": ["Seguimiento"],
        "summary": "Agrega una entrada al historial de avance",
        "description":
            "Las entradas NO se editan ni se borran. Un historial editable no "
            "es un historial: si una nota se puede cambiar despues, no sirve "
            "para reconstruir que se sabia en cada momento, que es para lo "
            "unico que existe.\\n\\n"
            "Solo se admite sobre planes APROBADA o EN_EJECUCION: registrar "
            "avance de algo que no empezo, o que ya termino, no describe nada.",
        "parameters": [{"name": "intervencion_id", "in": "path",
                        "required": True, "schema": {"type": "integer"}}],
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"type": "object",
                       "required": ["estado_reportado", "avance_nota"],
                       "properties": {
                           "estado_reportado": {
                               "type": "string",
                               "enum": ["EN_TIEMPO", "CON_RETRASO",
                                        "BLOQUEADA", "COMPLETADA"]},
                           "avance_nota": {"type": "string",
                                           "minLength": 10}}}}}},
        "responses": dict({"201": {"description": "Avance registrado"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/intervenciones/{intervencion_id}/evaluacion": {"post": {
        "tags": ["Evaluacion"],
        "summary": "Compara el antes y el despues sobre valores publicados",
        "description":
            "Dos cosas que este endpoint NO hace:\\n\\n"
            "1. No consume presupuesto de epsilon. Lee "
            "`agregado.v_tablero_unidad`, que son resultados ya publicados. "
            "Si evaluara llamando a la funcion de calculo, evaluar una "
            "intervencion gastaria privacidad y, al agotarla, dejaria a la "
            "campania sin poder publicar.\\n\\n"
            "2. No trata un valor suprimido como cero. Si el antes o el "
            "despues vino suprimido responde SIN_DATOS_SUFICIENTES con 200, y "
            "sin guardar nada: SIN_DATOS_SUFICIENTES es una respuesta de la "
            "API, no una conclusion almacenable.\\n\\n"
            "Tampoco atribuye causalidad: registra que la unidad se movio "
            "DESPUES de la intervencion, no que se movio POR ella.\\n\\n"
            "Una sola evaluacion por plan. La segunda responde 409 "
            "EVALUACION_YA_EXISTE, y el limite es deliberado: si se pudiera "
            "repetir con otro par de campanias, bastaria probar pares hasta "
            "encontrar el que deja bien a la intervencion.",
        "parameters": [{"name": "intervencion_id", "in": "path",
                        "required": True, "schema": {"type": "integer"}}],
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"type": "object",
                       "required": ["campania_antes", "campania_despues"],
                       "properties": {
                           "campania_antes": {"type": "string"},
                           "campania_despues": {"type": "string"},
                           "dimension_id": {"type": "string"}}}}}},
        "responses": dict({"200": {"description": "Evaluacion o SIN_DATOS"},
                           "201": {"description": "Evaluacion registrada"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Catalogo", "description": "Tipos de intervencion disponibles."},
    {"name": "Planes", "description": "Ciclo de vida de un plan."},
    {"name": "Seguimiento", "description": "Historial de avance, append-only."},
    {"name": "Evaluacion", "description": "Antes y despues sobre lo publicado."},
]


def montar(app):
    return registrar_openapi(
        app, "interventions-service — Bienestar Nexum",
        "Catalogo, diseno, administracion y seguimiento de intervenciones "
        "ORGANIZACIONALES.\\n\\n"
        "Una intervencion es una accion sobre una unidad: rediseniar un "
        "turno, revisar la carga de un equipo, abrir un espacio de "
        "acompaniamiento. Nunca sobre una persona, y eso no es una politica "
        "que el servicio recuerde aplicar: `intervencion.plan` no tiene "
        "columna para un empleado ni para un seudonimo, y la garantia G1 lo "
        "comprueba contra el catalogo del sistema.",
        rutas=RUTAS, esquemas=ESQUEMAS, etiquetas=ETIQUETAS)
