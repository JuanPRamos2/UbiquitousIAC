"""Contrato OpenAPI de algorithms-service.

El contrato documenta dos cosas que no se ven en la firma de los endpoints
y que son la razón de ser del servicio: evaluar el riesgo no consume
presupuesto de privacidad, y las unidades que el motor NO pudo evaluar se
reportan en lugar de omitirse.
"""
from comun.openapi import PARAMS_PAGINACION, RESPUESTAS_ERROR, registrar_openapi

NIVELES = ["INFORMATIVO", "ATENCION", "PRIORITARIO"]

ESQUEMAS = {
    "Regla": {
        "type": "object",
        "properties": {
            "regla_id": {"type": "string", "example": "RG-01"},
            "nombre": {"type": "string",
                       "example": "Carga percibida elevada de forma sostenida"},
            "condicion_legible": {
                "type": "string",
                "description": "La condición en palabras. No es decoración: es "
                               "lo que permite que alguien sin acceso al código "
                               "entienda por qué se disparó una detección, y lo "
                               "que hace auditable al motor."},
            "dimension_id": {"type": "string", "nullable": True,
                             "description": "Nulo cuando la regla evalúa el "
                                            "índice global."},
            "dimension": {"type": "string"},
            "umbral_valor": {"type": "number", "format": "double",
                             "nullable": True},
            "comparador": {"type": "string", "enum": ["<", "<=", ">", ">="],
                           "nullable": True},
            "campanias_consecutivas": {
                "type": "integer",
                "description": "Cuántas campañas seguidas tiene que cumplirse. "
                               "Una sola medición mala puede ser una semana "
                               "mala; tres seguidas son un patrón."},
            "nivel": {"type": "string", "enum": NIVELES},
            "activa": {"type": "boolean"},
            "detecciones_historicas": {"type": "integer"},
            "intervenciones_sugeridas": {
                "type": "array", "items": {"type": "string"},
                "description": "Tipos de intervención que la regla sugiere, en "
                               "orden. Son organizacionales: rediseño de turno, "
                               "revisión de carga, acompañamiento. Nunca "
                               "acciones sobre una persona."}}},
    "Deteccion": {
        "type": "object",
        "properties": {
            "deteccion_id": {"type": "string"},
            "regla_id": {"type": "string"},
            "unidad_organizacional_id": {"type": "string"},
            "unidad": {"type": "string"},
            "campania_id": {"type": "string"},
            "nivel": {"type": "string", "enum": NIVELES},
            "valor_observado": {"type": "number", "format": "double",
                                "nullable": True},
            "explicacion": {
                "type": "string",
                "description": "Qué valor se observó, contra qué umbral y en "
                               "qué campaña. Una detección sin explicación no "
                               "se emite: nadie aprueba un plan de "
                               "intervención porque un sistema lo diga."},
            "tipo_intervencion": {"type": "string", "nullable": True},
            "intervencion_sugerida": {"type": "string", "nullable": True},
            "orden": {"type": "integer", "nullable": True}}},
    "UnidadNoEvaluable": {
        "type": "object",
        "description": "Unidad convocada que el motor no pudo evaluar. Esta "
                       "lista es la parte que una implementación descuidada "
                       "omite: una unidad cuyos agregados se suprimieron todos "
                       "no aparece en las detecciones, y si no se reporta aquí, "
                       "la organización concluye que ahí no hay problema.",
        "properties": {
            "unidad_organizacional_id": {"type": "string"},
            "unidad": {"type": "string"},
            "plantilla_declarada": {"type": "integer"},
            "publicados": {"type": "integer", "example": 0},
            "suprimidos": {"type": "integer", "example": 3},
            "motivo": {"type": "string"}}},
    "SolicitudEvaluar": {
        "type": "object", "required": ["campania_id"],
        "properties": {
            "campania_id": {"type": "string", "example": "CAMP-2026-S1"},
            "unidad_organizacional_id": {
                "type": "string", "nullable": True,
                "description": "Sin este campo se evalúan todas las unidades "
                               "con algún agregado publicado en la campaña, "
                               "dentro del alcance del perfil."}}},
    "Corrida": {
        "type": "object",
        "properties": {
            "corrida_id": {"type": "string", "pattern": "^ALG-[0-9A-F]{12}$"},
            "campania_id": {"type": "string"},
            "unidad_organizacional_id": {"type": "string", "nullable": True},
            "unidades_evaluadas": {"type": "integer"},
            "detecciones": {"type": "array", "items": {
                "$ref": "#/components/schemas/Deteccion"}},
            "total_detecciones": {"type": "integer"},
            "por_nivel": {"type": "object",
                          "additionalProperties": {"type": "integer"}},
            "no_evaluables": {"type": "array", "items": {
                "$ref": "#/components/schemas/UnidadNoEvaluable"}},
            "total_no_evaluables": {"type": "integer"},
            "epsilon_consumido": {
                "type": "number", "format": "double", "example": 0,
                "description": "Siempre 0. El motor lee agregados ya "
                               "publicados; si recalculara para evaluar, cada "
                               "corrida gastaría presupuesto de privacidad y "
                               "evaluar el riesgo costaría la capacidad de "
                               "publicar resultados nuevos."},
            "ejecutado_por": {"type": "string"},
            "perfil_ejecutor": {"type": "string"},
            "fecha": {"type": "string", "format": "date-time"},
            "correlacion_id": {"type": "string"}}},
    "Cobertura": {
        "type": "object",
        "properties": {
            "campania_id": {"type": "string"},
            "unidades_convocadas": {"type": "integer"},
            "unidades_evaluables": {"type": "integer"},
            "unidades_no_evaluables": {"type": "integer"},
            "cobertura_porcentaje": {"type": "number", "format": "double",
                                     "nullable": True},
            "no_evaluables": {"type": "array", "items": {
                "$ref": "#/components/schemas/UnidadNoEvaluable"}},
            "nota": {"type": "string"}}},
    "SolicitudSimular": {
        "type": "object", "required": ["regla_id", "campania_id"],
        "properties": {
            "regla_id": {"type": "string", "example": "RG-02"},
            "campania_id": {"type": "string", "example": "CAMP-2026-S1"},
            "umbral_valor": {
                "type": "number", "format": "double", "example": 3.2,
                "description": "El umbral a probar. Sin este campo se usa el "
                               "actual, lo que sirve para ver el estado sin "
                               "cambiar nada."}}},
    "Simulacion": {
        "type": "object",
        "properties": {
            "regla_id": {"type": "string"},
            "nombre": {"type": "string"},
            "campania_id": {"type": "string"},
            "comparador": {"type": "string"},
            "umbral_actual": {"type": "number", "format": "double"},
            "umbral_simulado": {"type": "number", "format": "double"},
            "unidades_con_valor_publicado": {"type": "integer"},
            "detectadas_con_umbral_actual": {"type": "integer"},
            "detectadas_con_umbral_simulado": {"type": "integer"},
            "entrarian": {"type": "array", "items": {"type": "object"}},
            "saldrian": {"type": "array", "items": {"type": "object"}},
            "con_advertencia_de_precision": {
                "type": "integer",
                "description": "Unidades cuyo valor está cerca del ruido. Mover "
                               "el umbral unas décimas las mete o las saca por "
                               "azar y no por su situación real, así que se "
                               "cuentan aparte."},
            "nota": {"type": "string"},
            "epsilon_consumido": {"type": "number", "format": "double"}}},
}

RUTAS = {
    "/api/v1/algoritmos/reglas": {"get": {
        "tags": ["Reglas"],
        "summary": "Catálogo de reglas, con su condición en palabras",
        "description": "Cada regla trae su condición legible y los tipos de "
                       "intervención que sugiere. Las intervenciones son "
                       "organizacionales: rediseño de turno, revisión de carga, "
                       "acompañamiento. El sistema nunca sugiere una acción "
                       "sobre una persona, porque no produce resultados "
                       "individuales.",
        "responses": dict({"200": {
            "description": "Reglas del motor",
            "content": {"application/json": {"schema": {
                "type": "object",
                "properties": {
                    "reglas": {"type": "array", "items": {
                        "$ref": "#/components/schemas/Regla"}},
                    "total": {"type": "integer"}}}},
                "application/xml": {"schema": {"type": "string"},
                                    "example": '<reglas_respuesta xmlns="http://'
                                               'nexum.com.mx/bienestar/v1">…'
                                               '</reglas_respuesta>'}}}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/algoritmos/evaluar": {"post": {
        "tags": ["Evaluacion"],
        "summary": "Corre el motor sobre una campaña",
        "description": "Evalúa las reglas activas sobre los agregados **ya "
                       "publicados** y crea las detecciones. La corrida "
                       "completa queda guardada en MongoDB: qué reglas se "
                       "evaluaron, qué se detectó y qué unidades no se pudieron "
                       "evaluar. Sin ese registro, una detección de hace tres "
                       "meses no se puede explicar, porque los umbrales "
                       "pudieron cambiar desde entonces.\n\n"
                       "No consume épsilon: lee lo publicado, no recalcula.",
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/SolicitudEvaluar"},
            "examples": {
                "toda_la_campania": {
                    "summary": "Todas las unidades de la campaña",
                    "value": {"campania_id": "CAMP-2026-S1"}},
                "una_unidad": {
                    "summary": "Solo una unidad",
                    "value": {"campania_id": "CAMP-2026-S1",
                              "unidad_organizacional_id": "UO-CC-TURNO-B"}}}}}},
        "responses": dict({"201": {
            "description": "Corrida registrada",
            "content": {"application/json": {"schema": {
                "$ref": "#/components/schemas/Corrida"}}}}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/algoritmos/cobertura": {"get": {
        "tags": ["Evaluacion"],
        "summary": "Qué pudo ver el motor y qué no",
        "description": "Una unidad no evaluable **no** es una unidad sin "
                       "riesgo: es una unidad sobre la que el mecanismo de "
                       "privacidad no permite concluir nada. Distinguir las dos "
                       "cosas es la diferencia entre «no detectamos nada» y «no "
                       "pudimos ver».",
        "parameters": [{"name": "campania_id", "in": "query", "required": True,
                        "schema": {"type": "string"},
                        "example": "CAMP-2026-S1"}],
        "responses": dict({"200": {
            "description": "Cobertura de la evaluación",
            "content": {"application/json": {"schema": {
                "$ref": "#/components/schemas/Cobertura"}}}}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/algoritmos/detecciones": {"get": {
        "tags": ["Detecciones"],
        "summary": "Detecciones con su explicación y la intervención sugerida",
        "description": "El alcance se resuelve contra la jerarquía "
                       "organizacional y no contra el parámetro: un líder solo "
                       "ve su propio subárbol, aunque pida otra unidad en la "
                       "URL.",
        "parameters": PARAMS_PAGINACION + [
            {"name": "campania_id", "in": "query", "required": False,
             "schema": {"type": "string"}},
            {"name": "unidad_organizacional_id", "in": "query", "required": False,
             "schema": {"type": "string"}},
            {"name": "nivel", "in": "query", "required": False,
             "schema": {"type": "string", "enum": NIVELES}}],
        "responses": dict({"200": {
            "description": "Página de detecciones",
            "content": {"application/json": {"schema": {
                "type": "object",
                "properties": {
                    "detecciones": {"type": "array", "items": {
                        "$ref": "#/components/schemas/Deteccion"}},
                    "paginacion": {
                        "$ref": "#/components/schemas/Paginacion"}}}}}}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/algoritmos/simular": {"post": {
        "tags": ["Simulacion"],
        "summary": "Qué detectaría una regla con otro umbral. NO escribe",
        "description": "Permite a un comité mover un umbral con evidencia: "
                       "cuántas unidades más entrarían en atención, y cuáles. "
                       "La alternativa es cambiar el parámetro en producción y "
                       "ver qué pasa, que con datos de bienestar laboral no es "
                       "aceptable.\n\n"
                       "Es de solo lectura a propósito: una simulación que "
                       "dejara detecciones reales contaminaría el histórico con "
                       "escenarios que nunca ocurrieron.\n\n"
                       "Responde 400 si la regla evalúa una tendencia sostenida "
                       "en lugar de un umbral: ahí no hay un valor que simular.",
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/SolicitudSimular"},
            "examples": {
                "umbral_mas_estricto": {
                    "summary": "Subir el umbral de recuperación de 3.0 a 3.2",
                    "value": {"regla_id": "RG-02", "campania_id": "CAMP-2026-S1",
                              "umbral_valor": 3.2}}}}}},
        "responses": dict({"200": {
            "description": "Resultado de la simulación",
            "content": {"application/json": {"schema": {
                "$ref": "#/components/schemas/Simulacion"}}}}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/algoritmos/corridas": {"get": {
        "tags": ["Corridas"],
        "summary": "Historial de corridas del motor",
        "description": "Desde MongoDB, que es donde el proyecto almacena los "
                       "resultados de algoritmos. El listado no arrastra las "
                       "detecciones ni las unidades no evaluables: serían "
                       "cientos de elementos por página.",
        "parameters": PARAMS_PAGINACION + [
            {"name": "campania_id", "in": "query", "required": False,
             "schema": {"type": "string"}}],
        "responses": dict({"200": {"description": "Página de corridas"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/algoritmos/corridas/{corrida_id}": {"get": {
        "tags": ["Corridas"], "summary": "Una corrida con todo su detalle",
        "parameters": [{"name": "corrida_id", "in": "path", "required": True,
                        "schema": {"type": "string"},
                        "example": "ALG-4F2A91C7E803"}],
        "responses": dict({"200": {
            "description": "Corrida completa",
            "content": {"application/json": {"schema": {
                "$ref": "#/components/schemas/Corrida"}}}}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/algoritmos/indices": {"post": {
        "tags": ["Operacion"], "summary": "Declara los índices de la colección",
        "responses": dict({"200": {"description": "Índices creados"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Reglas", "description": "Catálogo del motor."},
    {"name": "Evaluacion", "description": "Corridas y cobertura."},
    {"name": "Detecciones", "description": "Lo detectado, con su explicación."},
    {"name": "Simulacion", "description": "Ajuste de umbrales sin escribir."},
    {"name": "Corridas", "description": "Historial en MongoDB."},
    {"name": "Operacion", "description": "Índices y mantenimiento."},
]


def montar(app):
    return registrar_openapi(
        app, "algorithms-service — Bienestar Nexum",
        "Motor de reglas de riesgo organizacional.\n\n"
        "Toma los agregados que **ya se publicaron**, evalúa las reglas del "
        "catálogo y produce detecciones con su explicación. Cuatro decisiones "
        "lo definen:\n\n"
        "1. **No consume épsilon.** Lee lo publicado en lugar de recalcular. Si "
        "recalculara, evaluar el riesgo de la organización costaría la "
        "capacidad de publicar resultados nuevos.\n"
        "2. **Una detección sin explicación no se emite.** Nadie aprueba un "
        "plan de intervención porque un sistema lo diga.\n"
        "3. **Las unidades que no se pudieron evaluar se reportan.** Omitirlas "
        "haría creer que ahí no hay riesgo, cuando lo que hay es falta de datos "
        "publicables.\n"
        "4. **La simulación no escribe.** Deja ajustar umbrales con evidencia "
        "sin contaminar el histórico con escenarios que nunca ocurrieron.\n\n"
        "La evaluación vive en `riesgo.fn_evaluar_unidad`, una función "
        "SECURITY DEFINER de PostgreSQL. El servicio no reimplementa las "
        "reglas: si lo hiciera, el portal y el microservicio podrían llegar a "
        "conclusiones distintas sobre los mismos datos.",
        RUTAS, ESQUEMAS, ETIQUETAS, puerto=8109)
