"""Contrato OpenAPI de export-service.

El contrato publica tres cosas que no se ven en la firma de los endpoints
y que son la razón de ser del servicio:

1. **Que generar y descargar son dos actos.** Dos permisos, dos registros.
   Un contrato que presentara la descarga como un detalle de la generación
   haría pensar que basta un permiso, y quien lo integre acabaría pidiendo
   el permiso de más.

2. **Por qué un conjunto de unidades se puede negar.** La selección es
   libre, y una selección libre de unidades de la misma rama permite
   calcular por resta una unidad que nunca se publicó. El error 403
   INFERENCIA_BLOQUEADA no es un límite de velocidad y conviene que el
   cliente lo distinga de uno.

3. **Que lo importado no se mezcla con lo calculado.** Quien integre este
   servicio tiene que saber que los valores que mete no van a aparecer en
   los tableros como agregados protegidos, porque no lo son.
"""
from comun.openapi import RESPUESTAS_ERROR, registrar_openapi

ESQUEMAS = {
    "FilaAgregado": {
        "type": "object",
        "description": "Una fila del archivo exportado. Las filas "
                       "SUPRIMIDAS tambien salen, con valor_protegido nulo "
                       "y su estado_publicacion: omitirlas haria leer «8 "
                       "unidades» donde hubo 12.",
        "properties": {
            "unidad_organizacional_id": {"type": "string",
                                         "example": "UO-CC-TURNO-B"},
            "unidad": {"type": "string"},
            "campania_id": {"type": "string", "example": "CAMP-2026-S4"},
            "dimension": {"type": "string"},
            "estado_publicacion": {
                "type": "string",
                "description": "PUBLICADO, o el motivo por el que no "
                               "(GRUPO_INSUFICIENTE, PRESUPUESTO_AGOTADO)."},
            "valor_protegido": {
                "type": "number", "format": "double", "nullable": True,
                "description": "Nulo cuando no se publico. NO es cero: es "
                               "ausencia de dato. En CSV se escribe «—» y "
                               "nunca una celda vacia, porque una celda "
                               "vacia se suma como cero en una hoja de "
                               "calculo y el promedio sale mas bajo que el "
                               "real."},
            "epsilon_aplicado": {"type": "number", "format": "double",
                                 "nullable": True},
            "mecanismo": {"type": "string", "nullable": True},
            "precision_advertencia": {"type": "string", "nullable": True},
        },
    },
    "Exportacion": {
        "type": "object",
        "properties": {
            "exportacion_id": {"type": "string", "example": "EXP-1A2B3C4D5E6F7A8B"},
            "formato": {"type": "string", "enum": ["json", "xml", "csv", "pdf"]},
            "sello_sha256": {
                "type": "string",
                "description": "SHA-256 del archivo. Se recalcula al "
                               "descargar sobre lo que se va a entregar: si "
                               "no coincide, no se entrega, porque "
                               "entregarlo con el sello viejo seria afirmar "
                               "una integridad que no hay."},
            "filas_publicadas": {"type": "integer"},
            "filas_suprimidas": {
                "type": "integer",
                "description": "Se cuenta aparte a proposito. «Exporte 8 "
                               "filas» y «exporte 8 de 12, 4 suprimidas» "
                               "describen situaciones distintas."},
            "estado": {"type": "string",
                       "enum": ["GENERADA", "DESCARGADA", "VENCIDA",
                                "RECHAZADA"]},
            "vence_en": {"type": "string", "format": "date-time"},
            "epsilon_consumido": {
                "type": "number", "example": 0.0,
                "description": "Siempre 0. Se lee de "
                               "agregado.v_tablero_unidad, que son "
                               "resultados ya publicados."},
        },
    },
    "RechazoFila": {
        "type": "object",
        "description": "Por que se rechazo una fila de la importacion. Se "
                       "informa fila por fila: un «no se pudo importar» sin "
                       "detalle obliga a adivinar, y quien sube el archivo "
                       "no tiene como arreglarlo.",
        "properties": {
            "fila": {"type": "integer"},
            "problema": {"type": "string"},
        },
    },
}

RUTAS = {
    "/api/v1/exportaciones/formatos": {"get": {
        "tags": ["Exportacion"],
        "summary": "Formatos disponibles y lo que cada uno conserva",
        "description":
            "Incluye por que la importacion NO admite PDF: un PDF es un "
            "formato de presentacion, extraer numeros de uno es adivinar "
            "donde empieza cada celda, y un dato de bienestar leido con "
            "heuristicas es peor que no tener el dato.",
        "responses": dict({"200": {"description": "Catalogo de formatos"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/exportaciones": {
        "get": {
            "tags": ["Exportacion"],
            "summary": "La bitacora de exportacion",
            "description":
                "Quien tiene BITACORA_CONSULTAR ve todas; el resto, solo las "
                "propias. Que un especialista vea las exportaciones de otro "
                "no aporta a su trabajo y si dice quien esta mirando que.\n\n"
                "Incluye las RECHAZADAS. Si solo se registraran las que "
                "salen, el intento de llevarse un conjunto que permite "
                "aislar a tres personas no habria existido nunca, y es "
                "justo el intento lo que hay que poder ver.",
            "parameters": [
                {"name": "pagina", "in": "query", "required": False,
                 "schema": {"type": "integer", "default": 1}},
                {"name": "tamano", "in": "query", "required": False,
                 "schema": {"type": "integer", "default": 20}},
            ],
            "responses": dict({"200": {"description": "Exportaciones paginadas"}},
                              **RESPUESTAS_ERROR)},
        "post": {
            "tags": ["Exportacion"],
            "summary": "Arma un archivo a partir de una seleccion libre",
            "description":
                "Permiso: EXPORTACION_GENERAR. **Generar no entrega el "
                "archivo**: descargarlo exige EXPORTACION_DESCARGAR y queda "
                "registrado aparte.\n\n"
                "ANTES de leer y de escribir un solo byte se revisa el "
                "CONJUNTO de unidades pedido. Un archivo con una unidad "
                "padre y tres de sus cuatro hijas contiene la cuarta por "
                "resta, aunque esa cuarta nunca se haya publicado y aunque "
                "las cuatro consultas, pedidas una a una en la pantalla, se "
                "hubieran bloqueado: fuera de aqui no hay ventana, ni "
                "actor, ni control ninguno. Ese caso responde 403 "
                "INFERENCIA_BLOQUEADA, con el residuo y el umbral en los "
                "detalles. No es un limite de velocidad.\n\n"
                "Tope de 5000 filas. Tampoco es un limite del servidor: un "
                "archivo de cien mil filas ya no lo revisa nadie antes de "
                "mandarlo.",
            "requestBody": {"required": True, "content": {"application/json": {
                "schema": {"type": "object",
                           "required": ["formato", "campanias", "unidades"],
                           "properties": {
                               "formato": {"type": "string",
                                           "enum": ["json", "xml", "csv", "pdf"]},
                               "campanias": {"type": "array",
                                             "items": {"type": "string"},
                                             "minItems": 1},
                               "unidades": {"type": "array",
                                            "items": {"type": "string"},
                                            "minItems": 1},
                               "dimensiones": {
                                   "type": "array",
                                   "items": {"type": "string"},
                                   "description": "Vacio = todas."}}}}}},
            "responses": dict({"201": {"description": "Archivo armado, no entregado"}},
                              **RESPUESTAS_ERROR)}},

    "/api/v1/exportaciones/{exportacion_id}": {"get": {
        "tags": ["Exportacion"],
        "summary": "Metadatos y el historial de descargas. No el archivo",
        "description":
            "El historial es una fila POR DESCARGA, no una bandera. Una "
            "tercera descarga del mismo archivo, una semana despues y desde "
            "otra cuenta, es una salida de datos distinta de la primera.",
        "parameters": [{"name": "exportacion_id", "in": "path",
                        "required": True, "schema": {"type": "string"}}],
        "responses": dict({"200": {"description": "Metadatos y descargas"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/exportaciones/{exportacion_id}/archivo": {"get": {
        "tags": ["Exportacion"],
        "summary": "Descarga el archivo. Permiso aparte y registro aparte",
        "description":
            "Permiso: EXPORTACION_DESCARGAR. Es el acto en que los datos "
            "salen de la organizacion, y por eso tiene su propio permiso y "
            "su propia fila.\n\n"
            "Entrega los bytes EXACTOS que se sellaron; no se regenera "
            "desde la seleccion. Si se regenerara, una campania publicada "
            "entre la generacion y la descarga daria un archivo distinto "
            "con el sello viejo, y el sello dejaria de servir para lo unico "
            "que sirve: demostrar que el archivo que alguien recibio es el "
            "que se genero.\n\n"
            "Un archivo vencido responde 410 EXPORTACION_VENCIDA y hay que "
            "volver a generarlo. Un enlace que no vence sigue sirviendo "
            "meses despues de que quien lo pidio dejo de necesitarlo, o "
            "dejo la organizacion.\n\n"
            "Cabeceras: `X-Exportacion-Sello` y "
            "`X-Exportacion-Suprimidas`, para que quien automatice la "
            "descarga pueda comprobar las dos cosas sin abrir el archivo.",
        "parameters": [{"name": "exportacion_id", "in": "path",
                        "required": True, "schema": {"type": "string"}}],
        "responses": dict({
            "200": {"description": "El archivo"},
            "409": {"description": "ARCHIVO_ALTERADO: el contenido no "
                                   "coincide con su sello"},
            "410": {"description": "EXPORTACION_VENCIDA"}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/importaciones/validar": {"post": {
        "tags": ["Importacion"],
        "summary": "Revisa un archivo contra el contrato. No aplica nada",
        "description":
            "Validar y aplicar estan separados por lo mismo que generar y "
            "descargar: revisar un archivo es inofensivo, y dar de alta "
            "agregados que vienen de fuera cambia lo que el sistema "
            "afirma.\n\n"
            "La validacion es contra el contrato Y contra los catalogos de "
            "la base, y la segunda importa mas: una fila puede tener todas "
            "sus columnas y referirse a una unidad que no existe. Darla de "
            "alta dejaria un agregado colgando de una unidad fantasma, que "
            "despues aparece en un tablero sin que nadie sepa de donde "
            "salio.\n\n"
            "`procedencia` es obligatoria. Un agregado sin procedencia es "
            "un numero sin dueno: dentro de seis meses nadie puede decir si "
            "salio de este sistema, de una hoja de calculo o de una "
            "estimacion.",
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"type": "object",
                       "required": ["formato", "procedencia", "contenido"],
                       "properties": {
                           "formato": {"type": "string",
                                       "enum": ["json", "xml", "csv"]},
                           "procedencia": {"type": "string", "minLength": 5},
                           "contenido": {
                               "type": "string",
                               "description": "El archivo como texto. Un "
                                              "CSV exportado por este mismo "
                                              "servicio se puede volver a "
                                              "importar sin editarlo: las "
                                              "lineas de comentario se "
                                              "saltan."}}}}}},
        "responses": dict({"201": {"description": "Validado, nada aplicado"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/importaciones/{importacion_id}": {"get": {
        "tags": ["Importacion"],
        "summary": "El resultado de la validacion, con los rechazos",
        "parameters": [{"name": "importacion_id", "in": "path",
                        "required": True, "schema": {"type": "string"}}],
        "responses": dict({"200": {"description": "Detalle de la importacion"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/importaciones/{importacion_id}/aplicar": {"post": {
        "tags": ["Importacion"],
        "summary": "Da de alta las filas validas, en su propia tabla",
        "description":
            "Permiso: IMPORTACION_APLICAR.\n\n"
            "Hay que volver a mandar el MISMO archivo. Se comprueba contra "
            "el sello guardado y, si no coincide, no se aplica: validar un "
            "archivo y aplicar otro seria el agujero mas obvio posible en "
            "un proceso de dos pasos.\n\n"
            "Lo aplicado va a `exportacion.agregado_externo` y NUNCA a los "
            "agregados calculados. Un agregado que viene de fuera no paso "
            "por el umbral k ni por el ruido de Laplace de este sistema: su "
            "numero puede venir de donde sea. Si se guardara en la misma "
            "tabla, dejaria de poder distinguirse un agregado protegido de "
            "uno que alguien escribio a mano. La separacion es fisica, no "
            "una columna de bandera que una consulta puede olvidar "
            "filtrar.",
        "parameters": [{"name": "importacion_id", "in": "path",
                        "required": True, "schema": {"type": "string"}}],
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"type": "object", "required": ["contenido"],
                       "properties": {"contenido": {"type": "string"}}}}}},
        "responses": dict({"200": {"description": "Filas aplicadas"},
                           "409": {"description": "SELLO_NO_COINCIDE, o ya "
                                                  "aplicada"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Exportacion",
     "description": "Egreso de agregados ya publicados, con control de "
                    "fuga por conjuntos pequenos."},
    {"name": "Importacion",
     "description": "Ingreso de agregados externos, validados y separados "
                    "de los calculados."},
]


def montar(app):
    return registrar_openapi(
        app, "export-service — Bienestar Nexum",
        "Egreso e ingreso controlado de agregados.\n\n"
        "QUE HACE QUE reports-service NO HAGA. reports-service exporta UN "
        "REPORTE: una forma fija que alguien reviso una vez. Este servicio "
        "exporta una SELECCION LIBRE, y la diferencia no es de tamano sino "
        "de riesgo: la selecion la arma quien exporta, cada vez, y el "
        "archivo fuera de aqui no tiene control ninguno.\n\n"
        "Ninguna operacion consume presupuesto de epsilon: todas leen "
        "resultados ya publicados.",
        rutas=RUTAS, esquemas=ESQUEMAS, etiquetas=ETIQUETAS)
