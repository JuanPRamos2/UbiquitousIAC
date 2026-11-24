"""Contrato OpenAPI de trends-service.

El contrato documenta la decisión que define al servicio y que no se ve en
la firma de ningún endpoint: **este servicio distingue un cambio real de un
movimiento del ruido, y publica el criterio con el que lo decide**.

Un servicio que clasifica cambios como reales o no reales sin decir con qué
regla es una caja negra, y una caja negra no se puede discutir en un comité
ni defender ante la unidad que recibe una intervención por su causa. Por eso
`/criterio` es parte del contrato y no una nota interna.

Igual que queries-service y reports-service, ninguna operación de aquí
consume presupuesto de épsilon: todas leen resultados ya publicados.
"""
from comun.openapi import RESPUESTAS_ERROR, registrar_openapi

ESQUEMAS = {
    "PuntoTendencia": {
        "type": "object",
        "description": "Un punto de la serie, con la lectura de su cambio "
                       "respecto al punto publicado anterior. Un punto "
                       "suprimido se conserva con valor nulo: quitarlo haria "
                       "que dos campanias no consecutivas parecieran "
                       "consecutivas y el salto entre ellas se leeria como un "
                       "solo paso.",
        "properties": {
            "campania_id": {"type": "string", "example": "CAMP-2026-S4"},
            "campania_nombre": {"type": "string", "nullable": True},
            "secuencia": {"type": "integer", "example": 4},
            "valor_protegido": {
                "type": "number", "format": "double", "nullable": True,
                "description": "Nulo cuando no se publico. NO es cero: es "
                               "ausencia de dato."},
            "n_observaciones": {"type": "integer", "nullable": True},
            "escala_ruido": {
                "type": "number", "format": "double", "nullable": True,
                "description": "Escala del ruido de Laplace aplicado al "
                               "publicar. Es lo que permite juzgar si una "
                               "diferencia cabe dentro del ruido."},
            "publicado": {"type": "boolean"},
            "cambio": {
                "type": "number", "format": "double", "nullable": True,
                "description": "Diferencia con el punto publicado anterior."},
            "umbral_de_ruido": {
                "type": "number", "format": "double",
                "description": "sqrt(2) * max(escala_a, escala_b). Por encima "
                               "de esto el cambio se considera real."},
            "supera_el_ruido": {
                "type": "boolean", "nullable": True,
                "description": "Nulo en el primer punto y en los suprimidos: "
                               "no hay con que comparar."},
            "campania_comparada": {"type": "string", "nullable": True},
            "lectura": {
                "type": "string",
                "description": "La interpretacion en palabras. Existe porque "
                               "un numero con signo no dice si vale la pena "
                               "mirarlo.",
                "example": "Cambio de -0.120 frente a CAMP-2026-S3, dentro "
                           "del ruido (umbral 0.283). No se puede afirmar que "
                           "haya cambiado nada."},
        },
    },
    "ResumenTendencia": {
        "type": "object",
        "description": "Direccion de la serie contando SOLO los cambios que "
                       "superan el ruido. Contar todos haria que una serie "
                       "plana con ruido pareciera tener movimiento: con seis "
                       "campanias, el azar produce tres subidas y tres "
                       "bajadas, y una de ellas siempre es la ultima.",
        "properties": {
            "campanias_publicadas": {"type": "integer"},
            "campanias_suprimidas": {"type": "integer"},
            "cambios_sobre_el_ruido": {"type": "integer"},
            "cambios_al_alza": {"type": "integer"},
            "cambios_a_la_baja": {"type": "integer"},
            "direccion": {
                "type": "string",
                "enum": ["AL_ALZA", "A_LA_BAJA", "MIXTA", "ESTABLE",
                         "INDETERMINADA"],
                "description": "ESTABLE no es 'no cambio': es que si cambio "
                               "algo, no se distingue del azar. "
                               "INDETERMINADA es que no hay suficientes "
                               "campanias publicadas para hablar de "
                               "tendencia."},
            "lectura": {"type": "string"},
        },
    },
}

RUTAS = {
    "/api/v1/tendencias/unidad/{unidad_id}": {"get": {
        "tags": ["Tendencias"],
        "summary": "Serie longitudinal de una unidad, con la lectura de cada cambio",
        "description":
            "Devuelve una serie POR DIMENSION. Una unidad no tiene una "
            "tendencia: tiene una por cada cosa que se le mide, y "
            "promediarlas esconderia que la carga empeora mientras el apoyo "
            "mejora.\n\n"
            "Para cada punto se dice si el movimiento respecto al anterior "
            "para cada punto, si el movimiento respecto al anterior supera el "
            "ruido.\n\n"
            "Es la pregunta que define al servicio: una unidad que paso de "
            "3.4 a 3.2 puede haber empeorado de verdad o puede ser azar, "
            "segun cuanto ruido se le aplico. Un tablero que dibuje las dos "
            "situaciones igual lleva a intervenir donde no paso nada y a no "
            "intervenir donde si.\n\n"
            "El alcance sale del perfil asignado y nunca del parametro: un "
            "lider solo ve su unidad y su subarbol.",
        "parameters": [
            {"name": "unidad_id", "in": "path", "required": True,
             "schema": {"type": "string"}},
            {"name": "dimension_id", "in": "query", "required": False,
             "schema": {"type": "string"},
             "description": "Limita la serie a una dimension."},
        ],
        "responses": dict({"200": {"description": "Serie con su resumen"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/tendencias/comparar": {"post": {
        "tags": ["Tendencias"],
        "summary": "Compara dos campanias en todas las unidades con alcance",
        "description":
            "Para cada unidad del alcance, el cambio entre dos campanias y si "
            "supera el ruido.\n\n"
            "Las que no se pudieron comparar van en `sin_comparacion`, con el "
            "motivo. Es la parte que una implementacion descuidada omite: una "
            "unidad sin valor publicado en alguna de las dos campanias no "
            "aparece en la comparacion, y si no se reporta, quien la lee "
            "concluye que ahi no hubo cambio cuando lo que pasa es que no se "
            "puede saber.",
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"type": "object",
                       "required": ["campania_base", "campania_comparada"],
                       "properties": {
                           "campania_base": {"type": "string",
                                             "example": "CAMP-2026-S3"},
                           "campania_comparada": {"type": "string",
                                                  "example": "CAMP-2026-S4"},
                           "dimension_id": {"type": "string"}}}}}},
        "responses": dict({"200": {"description": "Comparacion por unidad"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/tendencias/descensos": {"get": {
        "tags": ["Tendencias"],
        "summary": "Unidades con caidas sostenidas por encima del ruido",
        "description":
            "Las unidades cuya serie baja de forma sostenida, contando solo "
            "los cambios que superan el ruido.\n\n"
            "Alimenta la decision de intervenir, y por eso exige al menos "
            "tres puntos publicados: con dos, cualquier par de valores define "
            "una 'tendencia' que puede ser enteramente azar.",
        "parameters": [
            {"name": "dimension_id", "in": "query", "required": False,
             "schema": {"type": "string"}},
            {"name": "minimo_bajadas", "in": "query", "required": False,
             "schema": {"type": "integer", "default": 2}},
        ],
        "responses": dict({"200": {"description": "Unidades en descenso"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/tendencias/criterio": {"get": {
        "tags": ["Tendencias"],
        "summary": "La regla con la que el servicio decide, y sus limites",
        "description":
            "Publica el criterio y los limites conocidos.\n\n"
            "Esta aqui a proposito: un servicio que clasifica cambios como "
            "reales o no reales sin decir con que regla es una caja negra, y "
            "una caja negra no se puede discutir en un comite ni defender "
            "ante la unidad que recibe una intervencion por su causa.\n\n"
            "Incluye lo que el servicio NO hace: no es una prueba de "
            "hipotesis formal, y no extrapola, porque proyectar sobre valores "
            "con ruido produce una linea que se ve cientifica y no tiene "
            "sustento.",
        "responses": dict({"200": {"description": "El criterio"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Tendencias",
     "description": "Analisis longitudinal sobre resultados ya publicados."},
]


def montar(app):
    return registrar_openapi(
        app, "trends-service — Bienestar Nexum",
        "Analisis longitudinal y comparacion temporal de indicadores "
        "agregados.\n\n"
        "La pregunta que contesta es una sola: este cambio entre campanias, "
        "¿es real o cabe dentro del ruido? Ningun otro componente la "
        "contesta. queries-service devuelve la serie tal cual y no "
        "interpreta; algorithms-service evalua reglas sobre UNA campania.\n\n"
        "Ninguna operacion consume presupuesto de epsilon: todas leen "
        "resultados ya publicados.",
        rutas=RUTAS, esquemas=ESQUEMAS, etiquetas=ETIQUETAS)
