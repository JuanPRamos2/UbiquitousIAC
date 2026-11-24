"""Contrato OpenAPI de reports-service.

El contrato documenta las tres garantías que no se ven en la firma de los
endpoints y que son la razón de ser del servicio: no se consume épsilon, las
filas suprimidas se exportan con su motivo, y un reporte se sella y no se
edita.
"""
from comun.openapi import PARAMS_PAGINACION, RESPUESTAS_ERROR, registrar_openapi

TIPOS = ["TABLERO_CAMPANIA", "PARTICIPACION", "PRESUPUESTO_EPSILON",
         "SUPRESIONES", "INTERVENCIONES", "BITACORA_AUDITORIA",
         "RECOMENDACIONES"]

FORMATOS = ["json", "csv", "xml"]

ESQUEMAS = {
    "TipoReporte": {
        "type": "object",
        "properties": {
            "tipo": {"type": "string", "enum": TIPOS},
            "titulo": {"type": "string"},
            "nota": {"type": "string",
                     "description": "Qué significan las columnas y cómo NO debe "
                                    "leerse el reporte. Va en el contrato porque "
                                    "un CSV sin esta nota invita a tratar un "
                                    "valor con ruido como si fuera el promedio "
                                    "real de la unidad."},
            "parametro": {"type": "string", "nullable": True,
                          "description": "Nombre del parámetro que admite "
                                         "(campania_id, unidad_organizacional_id, "
                                         "accion) o nulo si no admite ninguno."},
            "parametro_obligatorio": {"type": "boolean"},
            "permisos": {"type": "array", "items": {"type": "string"},
                         "description": "Basta tener uno de ellos."},
            "formatos": {"type": "array", "items": {"type": "string",
                                                    "enum": FORMATOS}}}},
    "SolicitudReporte": {
        "type": "object", "required": ["tipo"],
        "properties": {
            "tipo": {"type": "string", "enum": TIPOS},
            "parametro": {"type": "string", "nullable": True,
                          "description": "El valor del parámetro que declara el "
                                         "tipo. TABLERO_CAMPANIA lo exige; los "
                                         "demás lo admiten como filtro."}}},
    "Reporte": {
        "type": "object",
        "description": "Metadatos del reporte generado. El contenido se descarga "
                       "aparte para no mandar miles de filas en cada listado.",
        "properties": {
            "reporte_id": {"type": "string", "pattern": "^RPT-[0-9A-F]{12}$"},
            "tipo": {"type": "string", "enum": TIPOS},
            "titulo": {"type": "string"},
            "nota": {"type": "string"},
            "parametro": {"type": "string", "nullable": True},
            "columnas": {"type": "array", "items": {"type": "string"}},
            "total_filas": {"type": "integer"},
            "filas_suprimidas": {
                "type": "integer",
                "description": "Cuántas de las filas van sin valor por supresión. "
                               "Se informa en los metadatos para que nadie "
                               "calcule una cobertura con el total y se quede con "
                               "una impresión equivocada."},
            "sello_sha256": {
                "type": "string", "pattern": "^[0-9a-f]{64}$",
                "description": "SHA-256 del contenido canónico. Permite "
                               "confrontar el archivo que recibió un tercero "
                               "contra lo que salió de aquí."},
            "generado_por": {"type": "string", "pattern": "^USR-[0-9]{5}$"},
            "perfil_generador": {"type": "string"},
            "fecha_generacion": {"type": "string", "format": "date-time"},
            "correlacion_id": {"type": "string"},
            "epsilon_consumido": {
                "type": "number", "format": "double", "example": 0,
                "description": "Siempre 0. Está en la respuesta a propósito: es "
                               "la prueba, por reporte, de que generarlo no gastó "
                               "presupuesto de privacidad."}}},
    "SolicitudVerificar": {
        "type": "object", "required": ["sello_sha256"],
        "properties": {
            "sello_sha256": {"type": "string", "pattern": "^[0-9a-fA-F]{64}$"}}},
    "Verificacion": {
        "type": "object",
        "properties": {
            "reporte_id": {"type": "string"},
            "coincide": {"type": "boolean",
                         "description": "El sello recibido es el del reporte."},
            "integro": {"type": "boolean",
                        "description": "El sello recalculado sobre las filas "
                                       "guardadas sigue dando el sello "
                                       "registrado: el documento almacenado no "
                                       "fue alterado."},
            "sello_registrado": {"type": "string"},
            "mensaje": {"type": "string"}}},
}

_CABECERAS_DESCARGA = {
    "X-Reporte-Sello": {
        "description": "El SHA-256 del reporte, también en la cabecera, para "
                       "poder verificar la descarga sin abrir el archivo.",
        "schema": {"type": "string"}},
    "X-Reporte-Filas-Suprimidas": {
        "description": "Cuántas filas del archivo van sin valor por supresión.",
        "schema": {"type": "integer"}},
    "Content-Disposition": {
        "description": "attachment con el nombre RPT-xxxx_tipo.ext",
        "schema": {"type": "string"}},
}

RUTAS = {
    "/api/v1/reportes/catalogo": {"get": {
        "tags": ["Catalogo"],
        "summary": "Reportes disponibles para quien pregunta",
        "description": "Se filtra por permisos: un colaborador no debe ver ni el "
                       "nombre del reporte de bitácora de auditoría.",
        "responses": dict({"200": {"description": "Tipos disponibles",
            "content": {"application/json": {"schema": {
                "type": "object",
                "properties": {
                    "elementos": {"type": "array", "items": {
                        "$ref": "#/components/schemas/TipoReporte"}},
                    "total": {"type": "integer"}}}}}}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/reportes": {
        "post": {
            "tags": ["Generacion"],
            "summary": "Genera un reporte y lo sella",
            "description": "Lee resultados YA publicados: no invoca "
                           "`agregado.fn_calcular_agregado_protegido` y por lo "
                           "tanto no consume épsilon.\n\n"
                           "El permiso se verifica dos veces: el decorador "
                           "comprueba que se tenga algún permiso de reportes, y "
                           "el cuerpo del endpoint comprueba el del tipo "
                           "concreto. Sin la segunda verificación, quien pudiera "
                           "generar el reporte de participación podría generar "
                           "el de bitácora.\n\n"
                           "Responde 404 SIN_DATOS si la consulta no devuelve "
                           "filas, en lugar de un reporte vacío: un archivo sin "
                           "filas se confunde con una campaña sin supresiones.",
            "requestBody": {"required": True, "content": {"application/json": {
                "schema": {"$ref": "#/components/schemas/SolicitudReporte"},
                "examples": {
                    "tablero": {"summary": "Resultados de una campaña",
                                "value": {"tipo": "TABLERO_CAMPANIA",
                                          "parametro": "CAMP-2026-S1"}},
                    "supresiones": {"summary": "Lo que no se publicó, y por qué",
                                    "value": {"tipo": "SUPRESIONES",
                                              "parametro": "CAMP-2026-S1"}},
                    "presupuesto": {"summary": "Épsilon, sin parámetro",
                                    "value": {"tipo": "PRESUPUESTO_EPSILON"}}}}}},
            "responses": dict({"201": {"description": "Reporte generado y sellado",
                "content": {"application/json": {"schema": {
                    "$ref": "#/components/schemas/Reporte"}}}}},
                **RESPUESTAS_ERROR)},
        "get": {
            "tags": ["Consulta"],
            "summary": "Reportes generados, del más reciente al más viejo",
            "description": "Solo se listan los tipos que quien pregunta podría "
                           "generar.",
            "parameters": PARAMS_PAGINACION + [
                {"name": "tipo", "in": "query", "required": False,
                 "schema": {"type": "string", "enum": TIPOS}},
                {"name": "mios", "in": "query", "required": False,
                 "schema": {"type": "string", "enum": ["1", "true", "si"]},
                 "description": "Solo los generados por quien pregunta."}],
            "responses": dict({"200": {"description": "Página de reportes",
                "content": {"application/json": {"schema": {
                    "type": "object",
                    "properties": {
                        "elementos": {"type": "array", "items": {
                            "$ref": "#/components/schemas/Reporte"}},
                        "paginacion": {
                            "$ref": "#/components/schemas/Paginacion"}}}}}}},
                **RESPUESTAS_ERROR)}},

    "/api/v1/reportes/{reporte_id}": {"get": {
        "tags": ["Consulta"], "summary": "Metadatos de un reporte",
        "parameters": [{"name": "reporte_id", "in": "path", "required": True,
                        "schema": {"type": "string"},
                        "example": "RPT-4F2A91C7E803"}],
        "responses": dict({"200": {"description": "Metadatos",
            "content": {"application/json": {"schema": {
                "$ref": "#/components/schemas/Reporte"}}}}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/reportes/{reporte_id}/contenido": {"get": {
        "tags": ["Descarga"],
        "summary": "Descarga el reporte en JSON, CSV o XML",
        "description": "Los tres formatos salen del MISMO documento guardado, no "
                       "de una consulta nueva: si se volviera a consultar la "
                       "base, el CSV y el JSON del mismo reporte podrían diferir "
                       "y el sello no cuadraría con ninguno.\n\n"
                       "El CSV va con comillas en todos los campos (la "
                       "explicación de una regla trae comas) y con BOM, para que "
                       "Excel en Windows abra los acentos sin preguntar nada.",
        "parameters": [
            {"name": "reporte_id", "in": "path", "required": True,
             "schema": {"type": "string"}},
            {"name": "formato", "in": "query", "required": False,
             "schema": {"type": "string", "enum": FORMATOS, "default": "json"}}],
        "responses": dict({"200": {"description": "Archivo del reporte",
            "headers": _CABECERAS_DESCARGA,
            "content": {
                "application/json": {"schema": {
                    "$ref": "#/components/schemas/Reporte"}},
                "text/csv": {"schema": {"type": "string"},
                             "example": '"campania_id","unidad","dimension",'
                                        '"estado_publicacion","valor_protegido"\r\n'
                                        '"CAMP-2026-S1","Centro de contacto turno B",'
                                        '"CARGA","PUBLICADO","3.4"\r\n'
                                        '"CAMP-2026-S1","Mantenimiento nocturno",'
                                        '"CARGA","GRUPO_INSUFICIENTE",""\r\n'},
                "application/xml": {"schema": {"type": "string"},
                                    "example": '<reporte xmlns="http://nexum.com.mx/'
                                               'bienestar/v1">…</reporte>'}}}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/reportes/{reporte_id}/grafica": {"get": {
        "tags": ["Reportes"],
        "summary": "Configuracion de Highcharts para el reporte",
        "description":
            "Devuelve la CONFIGURACION, no una imagen. El portal ya sirve "
            "Highcharts localmente y es quien tiene la pantalla; un "
            "microservicio que generara imagenes necesitaria un navegador "
            "sin interfaz dentro del contenedor —decenas de megabytes y una "
            "superficie de ataque nueva— para producir algo que el navegador "
            "del usuario dibuja gratis.\n\n"
            "Las filas suprimidas NO entran en la serie y su conteo viaja en "
            "el subtitulo. Meterlas como ceros moveria la grafica hacia abajo "
            "y haria ver un problema donde lo que hay es ausencia de dato.\n\n"
            "Un reporte sin columna numerica y sin columna de agrupacion "
            "responde `graficable: false` con el motivo, en lugar de una "
            "serie vacia.",
        "parameters": [{"name": "reporte_id", "in": "path", "required": True,
                        "schema": {"type": "string"}}],
        "responses": dict({"200": {"description": "Configuracion de la grafica"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/reportes/comparativo": {"post": {
        "tags": ["Reportes"],
        "summary": "Compara dos reportes ya generados del mismo tipo",
        "description":
            "Los datos salen de dos reportes YA GENERADOS, con sus dos "
            "sellos, no de dos consultas nuevas. Asi el comparativo se puede "
            "auditar —se sabe exactamente que dos fotos se restaron— y no "
            "consume presupuesto de epsilon.\n\n"
            "Las filas suprimidas en alguno de los dos NO se restan: se "
            "devuelven aparte en `sin_comparacion`, con el motivo. Restarlas "
            "contra cero produciria un numero que parece un hallazgo y es un "
            "artefacto.\n\n"
            "Cada fila comparada dice si la diferencia SUPERA la escala del "
            "ruido de los dos puntos. Una diferencia mas chica que el ruido "
            "puede ser enteramente azar, y sin ese campo alguien leeria una "
            "variacion de 0.1 como una mejora.",
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"type": "object",
                       "required": ["reporte_base", "reporte_comparado"],
                       "properties": {
                           "reporte_base": {"type": "string"},
                           "reporte_comparado": {"type": "string"}}}}}},
        "responses": dict({"200": {"description": "Comparativo"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/reportes/{reporte_id}/verificar": {"post": {
        "tags": ["Integridad"],
        "summary": "Confronta un sello contra el reporte guardado",
        "description": "Cierra el círculo de la evidencia: a un auditor le llegó "
                       "un archivo por correo y quiere saber si es el que salió "
                       "de aquí. Manda el sello, no el archivo.",
        "parameters": [{"name": "reporte_id", "in": "path", "required": True,
                        "schema": {"type": "string"}}],
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/SolicitudVerificar"},
            "examples": {"coincide": {"summary": "Sello del archivo recibido",
                "value": {"sello_sha256": "3b1f0c" + "0" * 58}}}}}},
        "responses": dict({"200": {"description": "Resultado de la confrontación",
            "content": {"application/json": {"schema": {
                "$ref": "#/components/schemas/Verificacion"}}}}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/reportes/indices": {"post": {
        "tags": ["Operacion"], "summary": "Declara los índices de la colección",
        "responses": dict({"200": {"description": "Índices creados"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Catalogo", "description": "Qué reportes existen y qué exigen."},
    {"name": "Generacion", "description": "Generación y sellado."},
    {"name": "Consulta", "description": "Metadatos de los reportes generados."},
    {"name": "Descarga", "description": "JSON, CSV y XML del mismo documento."},
    {"name": "Integridad", "description": "Verificación del sello."},
    {"name": "Operacion", "description": "Índices y mantenimiento."},
]


def montar(app):
    return registrar_openapi(
        app, "reports-service — Bienestar Nexum",
        "Genera, sella y entrega reportes a partir de resultados ya publicados.\n\n"
        "Tres garantías que el servicio hace cumplir y que son fáciles de "
        "romper sin que se note:\n\n"
        "1. **No consume épsilon.** Un reporte no calcula un agregado nuevo: lee "
        "lo ya publicado. Si lo calculara, bastarían unas cuantas descargas de "
        "CSV para dejar a la campaña sin poder publicar nada más.\n"
        "2. **Las filas suprimidas se exportan**, con su motivo y sin valor. Un "
        "CSV que las omitiera haría creer que la campaña tuvo menos unidades de "
        "las que tuvo, y exageraría la cobertura.\n"
        "3. **Un reporte se sella y no se edita.** Si los datos cambian, se "
        "genera un reporte nuevo con su propio sello; el viejo sigue siendo la "
        "foto de lo que se vio ese día.",
        RUTAS, ESQUEMAS, ETIQUETAS, puerto=8108)
