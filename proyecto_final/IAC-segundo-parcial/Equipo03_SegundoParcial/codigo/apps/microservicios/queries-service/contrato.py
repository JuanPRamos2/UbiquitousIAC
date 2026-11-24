"""Contrato OpenAPI de queries-service.

El contrato documenta una garantía que no es visible en la firma de los
endpoints y que es la razón de ser del servicio: ninguna de estas
operaciones consume presupuesto de épsilon. Todas leen resultados ya
publicados. Quien quiera un agregado nuevo pasa por el sistema web.
"""
from comun.openapi import RESPUESTAS_ERROR, registrar_openapi

RECURSOS = ["tablero", "tendencia", "presupuesto", "participacion", "catalogo"]

ESQUEMAS = {
    "FilaTablero": {
        "type": "object",
        "description": "Una dimensión de bienestar ya publicada para una unidad. "
                       "El valor viene del resultado protegido: trae ruido de "
                       "Laplace y puede venir suprimido.",
        "properties": {
            "unidad_organizacional_id": {"type": "string", "example": "UO-CC-TURNO-B"},
            "unidad": {"type": "string", "example": "Centro de contacto turno B"},
            "campania_id": {"type": "string", "example": "CAMP-2026-S1"},
            "secuencia": {"type": "integer", "example": 3},
            "dimension": {"type": "string", "example": "CARGA"},
            "estado_publicacion": {
                "type": "string",
                "enum": ["PUBLICADO", "GRUPO_INSUFICIENTE",
                         "PRESUPUESTO_PRIVACIDAD_AGOTADO"],
                "description": "La base distingue el motivo en lugar de un "
                               "generico 'suprimido': GRUPO_INSUFICIENTE es que "
                               "no se alcanzo el umbral k, y "
                               "PRESUPUESTO_PRIVACIDAD_AGOTADO es que la "
                               "campania ya gasto su epsilon. En ambos casos "
                               "valor_protegido viene nulo."},
            "participacion_protegida": {
                "type": "string", "nullable": True,
                "enum": ["suficiente", "insuficiente",
                         "no disponible: presupuesto de privacidad agotado"],
                "description": "Texto, no numero, y a proposito: devolver el "
                               "conteo exacto de participantes de un grupo chico "
                               "seria la via mas facil de deducir quien respondio."},
            "precision_advertencia": {"type": "boolean"},
            "valor_protegido": {"type": "number", "format": "double", "nullable": True},
            "epsilon_aplicado": {"type": "number", "format": "double",
                                 "description": "Épsilon que ya se gastó cuando se "
                                                "publicó este valor. Consultarlo "
                                                "aquí no gasta nada más."},
            "mecanismo": {"type": "string", "example": "LAPLACE"}}},
    "PuntoTendencia": {
        "type": "object",
        "description": "Un punto de la serie protegida de una unidad, tal como "
                       "lo devuelve agregado.v_tendencia. La variación es una "
                       "columna generada en la base, no un cálculo de este "
                       "servicio: así dos componentes no pueden reportar "
                       "variaciones distintas sobre los mismos datos.",
        "properties": {
            "unidad_organizacional_id": {"type": "string"},
            "unidad_nombre": {"type": "string"},
            "dimension_id": {"type": "string", "nullable": True},
            "secuencia": {"type": "integer"},
            "campania_id": {"type": "string"},
            "campania_nombre": {"type": "string"},
            "valor_protegido": {"type": "number", "format": "double",
                                "nullable": True},
            "n_observaciones": {"type": "integer", "nullable": True},
            "escala_ruido": {
                "type": "number", "format": "double", "nullable": True,
                "description": "Escala del ruido de Laplace aplicado. Viaja en "
                               "la respuesta porque es lo que permite juzgar si "
                               "una diferencia entre dos puntos es real o cabe "
                               "dentro del ruido."},
            "variacion_absoluta": {"type": "number", "format": "double",
                                   "nullable": True},
            "lectura": {
                "type": "string", "nullable": True,
                "description": "Lectura en palabras: la base compara la "
                               "variación contra la escala del ruido y no "
                               "reporta como cambio una diferencia que no se "
                               "puede distinguir del azar."}}},
    "EstadoPresupuesto": {
        "type": "object",
        "description": "Épsilon consumido y disponible por campaña y unidad. Es el "
                       "dato que decide si todavía se puede publicar un agregado.",
        "properties": {
            "campania_id": {"type": "string"},
            "unidad_organizacional_id": {"type": "string"},
            "epsilon_total": {"type": "number", "format": "double"},
            "epsilon_consumido": {"type": "number", "format": "double"},
            "epsilon_restante": {"type": "number", "format": "double"},
            "consultas_realizadas": {"type": "integer"},
            "agotado": {
                "type": "boolean",
                "description": "Cuando es verdadero, la base rechaza cualquier "
                               "publicacion nueva de esa campania y unidad: el "
                               "presupuesto es un tope real, no una advertencia."}}},
    "FilaParticipacion": {
        "type": "object",
        "description": "Conteos de respuesta, no puntajes. Aun así se marca el "
                       "grupo chico: un conteo de dos en una unidad de tres ya "
                       "dice demasiado sobre quién respondió.",
        "properties": {
            "campania_id": {"type": "string"},
            "unidad_organizacional_id": {"type": "string"},
            "unidad": {"type": "string"},
            "respuestas": {"type": "integer"},
            "plantilla_declarada": {"type": "integer"},
            "cobertura_porcentaje": {"type": "number", "format": "double",
                                     "nullable": True}}},
    "ResumenCatalogo": {
        "type": "object",
        "properties": {
            "unidades_activas": {"type": "integer"},
            "instrumentos_activos": {"type": "integer"},
            "campanias_abiertas": {"type": "integer"},
            "reactivos_activos": {"type": "integer"}}},
    "EstadoCache": {
        "type": "object",
        "description": "Aciertos y fallos por recurso. Sin números, un "
                       "'tenemos caché' no se puede defender en la demostración.",
        "properties": {
            "entradas": {"type": "integer"},
            "por_recurso": {
                "type": "object", "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "aciertos": {"type": "integer"},
                        "fallos": {"type": "integer"},
                        "tasa_acierto": {"type": "number", "format": "double"},
                        "ttl_segundos": {"type": "integer"}}}},
            "redis_disponible": {"type": "boolean"},
            "claves": {"type": "array", "items": {"type": "string"},
                       "description": "Las primeras 50 claves vigentes."}}},
    "SolicitudInvalidar": {
        "type": "object",
        "description": "Sin 'recurso' se invalida todo. Se invalida a propósito "
                       "cuando se publica un agregado nuevo: el tablero debe "
                       "reflejarlo de inmediato y no al minuto siguiente.",
        "properties": {
            "recurso": {"type": "string", "enum": RECURSOS}}},
}

_CABECERA_CACHE = {
    "X-Cache": {
        "description": "ACIERTO si la respuesta salió de Redis, FALLO si se "
                       "consultó PostgreSQL. Permite demostrar la caché sin "
                       "entrar al servidor.",
        "schema": {"type": "string", "enum": ["ACIERTO", "FALLO"]}},
    "X-Cache-TTL": {
        "description": "Segundos que esta entrada seguirá siendo válida.",
        "schema": {"type": "integer"}},
}


def _lista(nombre, clave, raiz):
    return {"application/json": {"schema": {
                "type": "object",
                "properties": {
                    clave: {"type": "array",
                            "items": {"$ref": f"#/components/schemas/{nombre}"}},
                    "desde_cache": {"type": "boolean"},
                    "ttl_segundos": {"type": "integer"},
                    "consultado_en": {"type": "string", "format": "date-time"}}}},
            "application/xml": {"schema": {"type": "string"},
                                "example": f"<{raiz} xmlns=\"http://nexum.com.mx/"
                                           f"bienestar/v1\">…</{raiz}>"}}


RUTAS = {
    "/api/v1/consultas/tablero/unidad/{unidad_id}": {"get": {
        "tags": ["Tableros"],
        "summary": "Tablero ya publicado de una unidad",
        "description": "Lee agregado.v_tablero_unidad. NO invoca "
                       "fn_calcular_agregado_protegido, así que recargar esta "
                       "pantalla cien veces no gasta ni un ápice de épsilon.\n\n"
                       "Responde 403 FUERA_DE_ALCANCE si la unidad no está en el "
                       "subárbol del alcance del perfil: el alcance se resuelve "
                       "con una consulta recursiva sobre la jerarquía, no con el "
                       "token.",
        "parameters": [
            {"name": "unidad_id", "in": "path", "required": True,
             "schema": {"type": "string"}, "example": "UO-CC-TURNO-B"},
            {"name": "campania_id", "in": "query", "required": False,
             "schema": {"type": "string"},
             "description": "Acota a una campaña. Sin este parámetro se "
                            "devuelven todas, de la más reciente a la más vieja."}],
        "responses": dict({"200": {"description": "Filas del tablero",
                                   "headers": _CABECERA_CACHE,
                                   "content": _lista("FilaTablero", "filas",
                                                     "tablero_respuesta")}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/consultas/tendencia": {"get": {
        "tags": ["Tableros"], "summary": "Serie de una unidad a lo largo de las campañas",
        "parameters": [
            {"name": "unidad_organizacional_id", "in": "query", "required": True,
             "schema": {"type": "string"}, "example": "UO-CC-TURNO-B"},
            {"name": "desde_campania", "in": "query", "required": False,
             "schema": {"type": "string"},
             "description": "Acota el inicio de la serie. El periodo se "
                            "expresa en campanias porque en este sistema la "
                            "campania ES el periodo de medicion: cada una "
                            "cubre un semestre. El corte se hace por "
                            "`secuencia` y no por el texto del "
                            "identificador, que ordenaria CAMP-2026-S10 "
                            "antes que CAMP-2026-S2."},
            {"name": "hasta_campania", "in": "query", "required": False,
             "schema": {"type": "string"},
             "description": "Acota el final de la serie. Una campania que no "
                            "existe responde 422 CAMPANIA_NO_EXISTE y no una "
                            "serie vacia: una serie vacia deja creer que la "
                            "unidad no tuvo resultados."},],
        "responses": dict({"200": {"description": "Puntos de la serie",
                                   "headers": _CABECERA_CACHE,
                                   "content": _lista("PuntoTendencia", "puntos",
                                                     "tendencia_respuesta")}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/consultas/presupuesto": {"get": {
        "tags": ["Privacidad"],
        "summary": "Épsilon consumido y disponible",
        "description": "TTL de caché de 10 segundos a propósito: un dato viejo "
                       "aquí llevaría a creer que queda presupuesto cuando ya "
                       "se agotó, y a intentar una publicación que la base va a "
                       "rechazar.",
        "responses": dict({"200": {"description": "Estado del presupuesto",
                                   "headers": _CABECERA_CACHE,
                                   "content": _lista("EstadoPresupuesto", "elementos",
                                                     "presupuesto_respuesta")}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/consultas/participacion": {"get": {
        "tags": ["Tableros"], "summary": "Cuántas personas respondieron, por unidad",
        "responses": dict({"200": {"description": "Conteos de participación",
                                   "headers": _CABECERA_CACHE,
                                   "content": _lista("FilaParticipacion", "elementos",
                                                     "participacion_respuesta")}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/consultas/catalogo/resumen": {"get": {
        "tags": ["Catalogo"], "summary": "Conteos de catálogo para encabezados",
        "description": "Los cuatro números que las pantallas muestran arriba. "
                       "TTL de 5 minutos: un catálogo cambia pocas veces al mes.",
        "responses": dict({"200": {"description": "Conteos",
                                   "headers": _CABECERA_CACHE,
                                   "content": {"application/json": {"schema": {
                                       "$ref": "#/components/schemas/ResumenCatalogo"}}}}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/consultas/cache/estado": {"get": {
        "tags": ["Cache"], "summary": "Aciertos, fallos y TTL por recurso",
        "responses": dict({"200": {"description": "Estado de la caché",
                                   "content": {"application/json": {"schema": {
                                       "$ref": "#/components/schemas/EstadoCache"}}}}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/consultas/cache/invalidar": {"post": {
        "tags": ["Cache"], "summary": "Invalida la caché de un recurso o de todos",
        "requestBody": {"required": False, "content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/SolicitudInvalidar"},
            "examples": {
                "un_recurso": {"summary": "Solo el tablero",
                               "value": {"recurso": "tablero"}},
                "todo": {"summary": "Todo (tras publicar agregados nuevos)",
                         "value": {}}}}}},
        "responses": dict({"200": {"description": "Entradas borradas"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Tableros", "description": "Lectura de resultados ya publicados."},
    {"name": "Privacidad", "description": "Estado del presupuesto de épsilon."},
    {"name": "Catalogo", "description": "Conteos de catálogo para encabezados."},
    {"name": "Cache", "description": "Observación e invalidación de la caché."},
]


def montar(app):
    return registrar_openapi(
        app, "queries-service — Bienestar Nexum",
        "Consultas de lectura con caché en Redis.\n\n"
        "La restricción que define al servicio: **nunca invoca "
        "`agregado.fn_calcular_agregado_protegido`**. Esa función consume "
        "presupuesto de épsilon cada vez que corre, de modo que un servicio de "
        "consultas que la llamara gastaría privacidad en cada recarga de "
        "pantalla y dejaría a la campaña sin poder publicar resultados nuevos. "
        "Aquí solo se leen las vistas de lo ya publicado.\n\n"
        "Cada respuesta trae las cabeceras `X-Cache` y `X-Cache-TTL` para poder "
        "demostrar la caché desde el navegador, sin entrar al servidor.",
        RUTAS, ESQUEMAS, ETIQUETAS, puerto=8107)
