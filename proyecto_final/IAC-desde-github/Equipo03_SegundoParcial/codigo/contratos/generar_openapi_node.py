"""
Genera el openapi.yaml de los dos microservicios en Node.

POR QUÉ UN GENERADOR Y NO UN YAML A MANO
----------------------------------------
catalog-service y main-process-service están escritos en Node y sirven su
contrato desde un archivo estático, así que no pueden construirlo con
comun/openapi.py como hacen los seis servicios en Python. Si ese YAML se
escribiera a mano, los dos documentarían un esquema de seguridad y un sobre
de error distintos a los que el módulo devuelve de verdad: es lo que pasaba
en la primera versión, donde el contrato declaraba el puerto 3002, una
sonda /health que no existe y ningún components.schemas.

Aquí se declara solo lo propio de cada servicio y la parte común —
seguridad, error, paginación, los siete códigos HTTP — sale de
comun.openapi.construir_contrato, la misma función que usan los servicios
en Python.

    python3 contratos/generar_openapi_node.py

Escribe apps/microservicios/<servicio>/openapi.yaml. El archivo generado no
se edita a mano.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "apps", "microservicios", "comun"))

import yaml                                                    # noqa: E402

from comun.openapi import (PARAMS_PAGINACION, RESPUESTAS_ERROR,  # noqa: E402
                           construir_contrato)

ESPACIO = "http://nexum.com.mx/bienestar/v1"


def ejemplo_xml(raiz, cuerpo):
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<{raiz} xmlns="{ESPACIO}">\n{cuerpo}\n</{raiz}>'


def dual(ref, raiz, cuerpo_xml):
    """Las dos representaciones de la misma respuesta: JSON y XML."""
    return {"application/json": {"schema": {"$ref": f"#/components/schemas/{ref}"}},
            "application/xml": {"schema": {"type": "string"},
                                "example": ejemplo_xml(raiz, cuerpo_xml)}}


PARAM_FORMATO = {
    "name": "formato", "in": "query", "required": False,
    "schema": {"type": "string", "enum": ["json", "xml"]},
    "description": "Alternativa a la cabecera Accept, para poder pedir XML "
                   "desde la barra de direcciones del navegador durante la "
                   "demostracion.",
}


def paginacion_catalogo():
    """Paginacion de catalog-service.

    Admite page/limit ADEMAS de pagina/tamano: la capa de datos del
    Integrante 2 los nombra en ingles y se conservan como alias en lugar de
    romper a un cliente que ya los use.
    """
    return PARAMS_PAGINACION + [
        {"name": "page", "in": "query", "required": False,
         "schema": {"type": "integer", "minimum": 1, "default": 1},
         "description": "Alias de 'pagina'."},
        {"name": "limit", "in": "query", "required": False,
         "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
         "description": "Alias de 'tamano'."},
    ]


# ===========================================================================
# catalog-service
# ===========================================================================

TIPO_UNIDAD = ["DIRECCION", "AREA", "DEPARTAMENTO", "TURNO", "EQUIPO"]
TIPO_INSTRUMENTO = ["NOM035", "CLIMA", "BREVE", "PERSONALIZADO"]
ESTADO_CAMPANIA = ["BORRADOR", "ABIERTA", "CERRADA", "CANCELADA"]

PAGINACION_REF = {"$ref": "#/components/schemas/Paginacion"}

ESQUEMAS_CATALOGO = {
    "UnidadOrganizacional": {
        "type": "object",
        "description": "Unidad del árbol organizacional. No desaparece nunca: se "
                       "marca inactiva. Un DELETE rompería las llaves foráneas de "
                       "las respuestas ya registradas.",
        "properties": {
            "unidad_organizacional_id": {"type": "string", "example": "UO-CC-TURNO-B"},
            "nombre": {"type": "string", "example": "Call Center - Turno B"},
            "descripcion": {"type": "string", "nullable": True},
            "tipo": {"type": "string", "enum": TIPO_UNIDAD},
            "unidad_padre_id": {"type": "string", "nullable": True,
                                "description": "Nulo solo en la raíz."},
            "nivel_jerarquico": {"type": "integer"},
            "plantilla_declarada": {
                "type": "integer",
                "description": "Personas declaradas en la unidad. Es el denominador "
                               "de la cobertura y el insumo del umbral k: una "
                               "unidad con plantilla de tres nunca podrá publicar "
                               "un agregado."},
            "activa": {"type": "boolean"},
            "fecha_creacion": {"type": "string", "format": "date-time"},
            "fecha_actualizacion": {"type": "string", "format": "date-time"}}},
    "Instrumento": {
        "type": "object",
        "properties": {
            "instrumento_id": {"type": "string", "example": "INST-BIENESTAR"},
            "nombre": {"type": "string"},
            "descripcion": {"type": "string", "nullable": True},
            "tipo": {"type": "string", "enum": TIPO_INSTRUMENTO},
            "fuente_id": {
                "type": "string", "example": "FUENTE-AUTOREPORTE",
                "description": "Fuente autorizada. Obligatorio: un instrumento "
                               "psicométrico sin fuente declarada no se puede "
                               "defender ante una revisión."},
            "activo": {"type": "boolean"},
            "fecha_creacion": {"type": "string", "format": "date-time"},
            "fecha_actualizacion": {"type": "string", "format": "date-time"}}},
    "VersionInstrumento": {
        "type": "object",
        "description": "La escala vive aquí y no en el reactivo: el mismo reactivo "
                       "puede medirse 1-5 en una versión y 1-7 en la siguiente, y "
                       "los agregados de campañas viejas tienen que seguir "
                       "interpretándose con la escala vigente cuando se "
                       "respondieron.",
        "properties": {
            "instrumento_id": {"type": "string"},
            "version": {"type": "integer", "minimum": 1},
            "fecha_vigencia_desde": {"type": "string", "format": "date"},
            "fecha_vigencia_hasta": {"type": "string", "format": "date",
                                     "nullable": True},
            "escala_min": {"type": "integer", "example": 1},
            "escala_max": {"type": "integer", "example": 5},
            "publicada": {"type": "boolean"},
            "activa": {"type": "boolean"},
            "fecha_creacion": {"type": "string", "format": "date-time"},
            "fecha_actualizacion": {"type": "string", "format": "date-time"}}},
    "Reactivo": {
        "type": "object",
        "properties": {
            "reactivo_id": {"type": "string", "pattern": "^R-[0-9]{2,3}$",
                            "example": "R-01"},
            "texto": {"type": "string"},
            "dimension_id": {"type": "string", "nullable": True,
                             "example": "DIM-CARGA"},
            "invertido": {
                "type": "boolean",
                "description": "Reactivo de redacción inversa: una respuesta alta "
                               "significa peor, no mejor. Sin este campo el índice "
                               "se sumaría al revés y el resultado se vería "
                               "plausible estando mal."},
            "activo": {"type": "boolean"},
            "fecha_creacion": {"type": "string", "format": "date-time"},
            "fecha_actualizacion": {"type": "string", "format": "date-time"}}},
    "ReactivoDeVersion": {
        "type": "object",
        "description": "Reactivo tal como aparece DENTRO de una versión: con su "
                       "orden, si es obligatorio y con qué escala se responde. Es "
                       "lo que el portal necesita para pintar el cuestionario.",
        "properties": {
            "reactivo_id": {"type": "string"},
            "texto": {"type": "string"},
            "dimension_id": {"type": "string", "nullable": True},
            "invertido": {"type": "boolean"},
            "activo": {"type": "boolean"},
            "orden": {"type": "integer", "minimum": 1},
            "obligatorio": {"type": "boolean"},
            "escala_min": {"type": "integer"},
            "escala_max": {"type": "integer"}}},
    "Campania": {
        "type": "object",
        "properties": {
            "campania_id": {"type": "string", "example": "CAMP-2026-S1"},
            "nombre": {"type": "string"},
            "instrumento_id": {"type": "string"},
            "version_instrumento": {"type": "integer"},
            "fecha_inicio": {"type": "string", "format": "date"},
            "fecha_fin": {"type": "string", "format": "date"},
            "estado": {
                "type": "string", "enum": ESTADO_CAMPANIA,
                "description": "Cuatro estados, no un booleano: BORRADOR permite "
                               "preparar una campaña sin que nadie la pueda "
                               "responder, y CANCELADA la cierra sin pretender "
                               "que produjo resultados."},
            "secuencia": {"type": "integer",
                          "description": "Orden en la serie histórica. Permite "
                                         "hablar de tendencia sin depender de las "
                                         "fechas, que pueden moverse."},
            "fecha_creacion": {"type": "string", "format": "date-time"},
            "fecha_actualizacion": {"type": "string", "format": "date-time"}}},
    "Dimension": {
        "type": "object",
        "properties": {
            "dimension_id": {"type": "string", "example": "DIM-CARGA"},
            "nombre": {"type": "string"},
            "descripcion": {"type": "string", "nullable": True},
            "orden": {"type": "integer"}}},
    "FuenteAutorizada": {
        "type": "object",
        "description": "Incluye filas con autorizada=false (correo, chat, GPS, "
                       "teclado, navegación): están ahí para dejar por escrito lo "
                       "que el sistema NO puede medir. Por eso el catálogo es de "
                       "solo lectura: un endpoint de escritura permitiría "
                       "autorizarlas.",
        "properties": {
            "fuente_id": {"type": "string"},
            "nombre": {"type": "string"},
            "descripcion": {"type": "string", "nullable": True},
            "autorizada": {"type": "boolean"},
            "motivo": {"type": "string", "nullable": True}}},
}


def _lista_catalogo(plural, singular_ref, raiz):
    return {
        "type": "object",
        "properties": {
            plural: {"type": "array",
                     "items": {"$ref": f"#/components/schemas/{singular_ref}"}},
            "paginacion": PAGINACION_REF,
            "desde_cache": {"type": "boolean",
                            "description": "La respuesta salió de Redis."}},
    }


for _plural, _ref in [("unidades", "UnidadOrganizacional"),
                      ("instrumentos", "Instrumento"),
                      ("versiones", "VersionInstrumento"),
                      ("reactivos", "Reactivo"),
                      ("campanias", "Campania")]:
    ESQUEMAS_CATALOGO[f"Lista{_plural.capitalize()}"] = _lista_catalogo(
        _plural, _ref, f"{_plural}_respuesta")

ESQUEMAS_CATALOGO["ListaReactivosVersion"] = _lista_catalogo(
    "reactivos", "ReactivoDeVersion", "reactivos_version_respuesta")


def _crud(recurso, singular, ref, permiso_escritura, id_ejemplo,
          obligatorios, ejemplo_alta):
    """Las cinco operaciones de un recurso de catálogo.

    La baja es lógica en las cinco: DELETE responde 200 con la entidad
    marcada inactiva, no 204 sin cuerpo. Devolver la entidad es deliberado:
    el cliente ve que sigue existiendo y que lo que cambió fue 'activa'.
    """
    plural_schema = f"Lista{recurso.capitalize()}"
    return {
        f"/api/v1/catalogos/{recurso}": {
            "get": {
                "tags": [recurso.capitalize()],
                "summary": f"Listar {recurso}",
                "description": "Lectura abierta a los cinco perfiles, cada uno por "
                               "un motivo distinto: el colaborador para ver los "
                               "reactivos que va a responder, el líder y el "
                               "especialista para interpretar un agregado, el "
                               "auditor para revisar qué instrumento se aplicó, el "
                               "administrador para operar. Aun así exige token: el "
                               "catálogo revela la estructura de la empresa.",
                "parameters": paginacion_catalogo() + [PARAM_FORMATO],
                "responses": dict({"200": {
                    "description": f"Página de {recurso}",
                    "headers": {"X-Cache": {
                        "description": "ACIERTO si la respuesta salió de Redis.",
                        "schema": {"type": "string",
                                   "enum": ["ACIERTO", "FALLO"]}}},
                    "content": dual(plural_schema, f"{recurso}_respuesta",
                                    f"  <{recurso}>…</{recurso}>\n  <paginacion>…</paginacion>")},
                }, **RESPUESTAS_ERROR)},
            "post": {
                "tags": [recurso.capitalize()],
                "summary": f"Crear {singular}",
                "description": f"Exige el permiso {permiso_escritura}.",
                "requestBody": {"required": True, "content": {"application/json": {
                    "schema": {"$ref": f"#/components/schemas/{ref}",
                               "required": obligatorios},
                    "example": ejemplo_alta}}},
                "responses": dict({"201": {
                    "description": f"{singular.capitalize()} creado",
                    "content": dual(ref, f"{singular}_respuesta",
                                    f"  <{singular}>…</{singular}>")}},
                    **RESPUESTAS_ERROR)}},
        f"/api/v1/catalogos/{recurso}/{{id}}": {
            "get": {
                "tags": [recurso.capitalize()],
                "summary": f"Consultar un {singular}",
                "parameters": [{"name": "id", "in": "path", "required": True,
                                "schema": {"type": "string"},
                                "example": id_ejemplo}, PARAM_FORMATO],
                "responses": dict({"200": {
                    "description": singular.capitalize(),
                    "content": dual(ref, f"{singular}_respuesta",
                                    f"  <{singular}>…</{singular}>")}},
                    **RESPUESTAS_ERROR)},
            "put": {
                "tags": [recurso.capitalize()],
                "summary": f"Modificar un {singular}",
                "description": f"Exige el permiso {permiso_escritura}.",
                "parameters": [{"name": "id", "in": "path", "required": True,
                                "schema": {"type": "string"}}],
                "requestBody": {"required": True, "content": {"application/json": {
                    "schema": {"$ref": f"#/components/schemas/{ref}"}}}},
                "responses": dict({"200": {
                    "description": f"{singular.capitalize()} modificado",
                    "content": dual(ref, f"{singular}_respuesta",
                                    f"  <{singular}>…</{singular}>")}},
                    **RESPUESTAS_ERROR)},
            "delete": {
                "tags": [recurso.capitalize()],
                "summary": f"Baja LÓGICA de un {singular}",
                "description": "No borra: marca la entidad inactiva y la devuelve. "
                               "Un DELETE real rompería las llaves foráneas de las "
                               "respuestas ya registradas, o dejaría huérfano el "
                               "histórico de agregados. Responde 200 con la "
                               "entidad, no 204 sin cuerpo, para que el cliente vea "
                               "que sigue existiendo y que lo que cambió fue el "
                               "campo de actividad.",
                "parameters": [{"name": "id", "in": "path", "required": True,
                                "schema": {"type": "string"}}],
                "responses": dict({"200": {
                    "description": f"{singular.capitalize()} marcado inactivo",
                    "content": dual(ref, f"{singular}_respuesta",
                                    f"  <{singular}>…</{singular}>")}},
                    **RESPUESTAS_ERROR)}},
    }


RUTAS_CATALOGO = {}
RUTAS_CATALOGO.update(_crud(
    "unidades", "unidad", "UnidadOrganizacional", "UNIDAD_ADMIN",
    "UO-CC-TURNO-B", ["unidad_organizacional_id", "nombre"],
    {"unidad_organizacional_id": "UO-CC-TURNO-C", "nombre": "Call Center - Turno C",
     "tipo": "TURNO", "unidad_padre_id": "UO-OPERACIONES",
     "plantilla_declarada": 18}))
RUTAS_CATALOGO.update(_crud(
    "instrumentos", "instrumento", "Instrumento", "INSTRUMENTO_ADMIN",
    "INST-BIENESTAR", ["instrumento_id", "nombre", "tipo", "fuente_id"],
    {"instrumento_id": "INST-CLIMA", "nombre": "Encuesta breve de clima",
     "tipo": "CLIMA", "fuente_id": "FUENTE-AUTOREPORTE"}))
RUTAS_CATALOGO.update(_crud(
    "reactivos", "reactivo", "Reactivo", "INSTRUMENTO_ADMIN", "R-01",
    ["reactivo_id", "texto"],
    {"reactivo_id": "R-21", "texto": "Puedo desconectarme al terminar mi jornada.",
     "dimension_id": "DIM-RECUP", "invertido": False}))
RUTAS_CATALOGO.update(_crud(
    "campanias", "campania", "Campania", "CAMPANIA_ADMIN", "CAMP-2026-S1",
    ["campania_id", "nombre", "instrumento_id", "version_instrumento",
     "fecha_inicio", "fecha_fin"],
    {"campania_id": "CAMP-2026-S6", "nombre": "Medición semestral 6",
     "instrumento_id": "INST-BIENESTAR", "version_instrumento": 1,
     "fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-15"}))

RUTAS_CATALOGO.update({
    "/api/v1/catalogos/instrumentos/{id}/versiones": {
        "get": {
            "tags": ["Versiones"], "summary": "Versiones de un instrumento",
            "parameters": [{"name": "id", "in": "path", "required": True,
                            "schema": {"type": "string"},
                            "example": "INST-BIENESTAR"}, PARAM_FORMATO],
            "responses": dict({"200": {
                "description": "Versiones",
                "content": dual("ListaVersiones", "versiones_respuesta",
                                "  <versiones>…</versiones>")}},
                **RESPUESTAS_ERROR)},
        "post": {
            "tags": ["Versiones"], "summary": "Crear una versión",
            "description": "Exige INSTRUMENTO_ADMIN. Una versión nueva no modifica "
                           "las respuestas ya registradas con la versión anterior: "
                           "por eso se versiona en lugar de editar los reactivos "
                           "en su lugar.",
            "parameters": [{"name": "id", "in": "path", "required": True,
                            "schema": {"type": "string"}}],
            "requestBody": {"required": True, "content": {"application/json": {
                "schema": {"$ref": "#/components/schemas/VersionInstrumento"},
                "example": {"version": 2, "fecha_vigencia_desde": "2027-01-01",
                            "escala_min": 1, "escala_max": 7,
                            "publicada": False}}}},
            "responses": dict({"201": {
                "description": "Versión creada",
                "content": dual("VersionInstrumento", "version_respuesta",
                                "  <version>…</version>")}},
                **RESPUESTAS_ERROR)}},
    "/api/v1/catalogos/instrumentos/{id}/versiones/{version}": {
        "get": {
            "tags": ["Versiones"], "summary": "Consultar una versión",
            "parameters": [
                {"name": "id", "in": "path", "required": True,
                 "schema": {"type": "string"}},
                {"name": "version", "in": "path", "required": True,
                 "schema": {"type": "integer"}}, PARAM_FORMATO],
            "responses": dict({"200": {
                "description": "Versión",
                "content": dual("VersionInstrumento", "version_respuesta",
                                "  <version>…</version>")}},
                **RESPUESTAS_ERROR)},
        "put": {
            "tags": ["Versiones"], "summary": "Modificar una versión",
            "parameters": [
                {"name": "id", "in": "path", "required": True,
                 "schema": {"type": "string"}},
                {"name": "version", "in": "path", "required": True,
                 "schema": {"type": "integer"}}],
            "requestBody": {"required": True, "content": {"application/json": {
                "schema": {"$ref": "#/components/schemas/VersionInstrumento"}}}},
            "responses": dict({"200": {
                "description": "Versión modificada",
                "content": dual("VersionInstrumento", "version_respuesta",
                                "  <version>…</version>")}},
                **RESPUESTAS_ERROR)},
        "delete": {
            "tags": ["Versiones"], "summary": "Baja lógica de una versión",
            "parameters": [
                {"name": "id", "in": "path", "required": True,
                 "schema": {"type": "string"}},
                {"name": "version", "in": "path", "required": True,
                 "schema": {"type": "integer"}}],
            "responses": dict({"200": {
                "description": "Versión marcada inactiva",
                "content": dual("VersionInstrumento", "version_respuesta",
                                "  <version>…</version>")}},
                **RESPUESTAS_ERROR)}},
    "/api/v1/catalogos/instrumentos/{instrumento_id}/versiones/{version}/reactivos": {
        "get": {
            "tags": ["Versiones"],
            "summary": "Reactivos de una versión, en su orden",
            "description": "Es la consulta que usa el portal para pintar el "
                           "cuestionario: trae el texto, el orden, si el reactivo "
                           "es obligatorio y con qué escala se responde.",
            "parameters": [
                {"name": "instrumento_id", "in": "path", "required": True,
                 "schema": {"type": "string"}, "example": "INST-BIENESTAR"},
                {"name": "version", "in": "path", "required": True,
                 "schema": {"type": "integer"}, "example": 1}, PARAM_FORMATO],
            "responses": dict({"200": {
                "description": "Reactivos de la versión",
                "content": dual("ListaReactivosVersion",
                                "reactivos_version_respuesta",
                                "  <reactivos>…</reactivos>")}},
                **RESPUESTAS_ERROR)},
        "post": {
            "tags": ["Versiones"], "summary": "Asociar un reactivo a la versión",
            "parameters": [
                {"name": "instrumento_id", "in": "path", "required": True,
                 "schema": {"type": "string"}},
                {"name": "version", "in": "path", "required": True,
                 "schema": {"type": "integer"}}],
            "requestBody": {"required": True, "content": {"application/json": {
                "schema": {"type": "object",
                           "required": ["reactivo_id", "orden"],
                           "properties": {
                               "reactivo_id": {"type": "string", "example": "R-21"},
                               "orden": {"type": "integer", "example": 21},
                               "obligatorio": {"type": "boolean", "default": True}}},
                "example": {"reactivo_id": "R-21", "orden": 21,
                            "obligatorio": True}}}},
            "responses": dict({"201": {"description": "Reactivo asociado"}},
                              **RESPUESTAS_ERROR)}},
    "/api/v1/catalogos/instrumentos/{instrumento_id}/versiones/{version}/reactivos/{reactivo_id}": {
        "delete": {
            "tags": ["Versiones"],
            "summary": "Desasociar un reactivo de la versión",
            "description": "Aquí sí hay borrado real, y es correcto: la tabla es de "
                           "relación. Quitar un reactivo de una versión no borra el "
                           "reactivo ni ninguna respuesta ya registrada.",
            "parameters": [
                {"name": "instrumento_id", "in": "path", "required": True,
                 "schema": {"type": "string"}},
                {"name": "version", "in": "path", "required": True,
                 "schema": {"type": "integer"}},
                {"name": "reactivo_id", "in": "path", "required": True,
                 "schema": {"type": "string"}}],
            "responses": dict({"200": {"description": "Reactivo desasociado"}},
                              **RESPUESTAS_ERROR)}},
    "/api/v1/catalogos/dimensiones": {
        "get": {
            "tags": ["Apoyo"], "summary": "Dimensiones del instrumento",
            "description": "Solo lectura: las dimensiones las define la metodología "
                           "del instrumento, no la operación del sistema.",
            "parameters": [PARAM_FORMATO],
            "responses": dict({"200": {
                "description": "Dimensiones",
                "content": {"application/json": {"schema": {
                    "type": "object",
                    "properties": {
                        "dimensiones": {"type": "array", "items": {
                            "$ref": "#/components/schemas/Dimension"}},
                        "total": {"type": "integer"}}}}}}},
                **RESPUESTAS_ERROR)}},
    "/api/v1/catalogos/fuentes": {
        "get": {
            "tags": ["Apoyo"], "summary": "Fuentes de dato autorizadas y vedadas",
            "description": "Solo lectura, y por una razón de gobernanza: la tabla "
                           "incluye filas con autorizada=false (correo, chat, GPS, "
                           "teclado, navegación) que dejan por escrito lo que el "
                           "sistema no puede medir. Un endpoint de escritura "
                           "permitiría autorizarlas.",
            "parameters": [PARAM_FORMATO],
            "responses": dict({"200": {
                "description": "Fuentes",
                "content": {"application/json": {"schema": {
                    "type": "object",
                    "properties": {
                        "fuentes": {"type": "array", "items": {
                            "$ref": "#/components/schemas/FuenteAutorizada"}},
                        "total": {"type": "integer"}}}}}}},
                **RESPUESTAS_ERROR)}},
})

ETIQUETAS_CATALOGO = [
    {"name": "Unidades", "description": "Árbol organizacional."},
    {"name": "Instrumentos", "description": "Instrumentos psicométricos."},
    {"name": "Versiones", "description": "Versiones y sus reactivos."},
    {"name": "Reactivos", "description": "Preguntas del instrumento."},
    {"name": "Campanias", "description": "Campañas de medición."},
    {"name": "Apoyo", "description": "Catálogos de solo lectura."},
]

DESCRIPCION_CATALOGO = """\
CRUD de unidades organizacionales, instrumentos, versiones, reactivos y
campañas sobre PostgreSQL. **Integrante 2 (Ricardo Arath Sánchez Aguirre).**

Tres decisiones que recorren todo el servicio:

1. **La baja es lógica.** `DELETE` marca la entidad inactiva y la devuelve;
   nunca borra. Un borrado real rompería las llaves foráneas de las
   respuestas ya registradas, o dejaría huérfano el histórico de agregados.
   Las únicas excepciones son las tablas de relación (`reactivo_version`,
   `campania_unidad`), donde desasociar no destruye nada.

2. **La autorización se expresa con permisos, no con perfiles.** El día que
   el equipo cree un perfil nuevo ("coordinador de turno") basta con
   asignarle permisos en `usuarios.perfil_permiso` y estas rutas lo aceptan
   sin recompilar. Si la lista fuera de perfiles, habría que editar el
   código y volver a desplegar.

3. **Leer el catálogo también exige token.** El catálogo revela la
   estructura organizacional de la empresa, incluida la plantilla declarada
   de cada unidad.

La caché en Redis se invalida en cada mutación y cada listado informa, en
la cabecera `X-Cache` y en el campo `desde_cache`, si la respuesta salió de
la caché o de la base.

Todas las respuestas existen en JSON y en XML: `Accept: application/xml` o
`?formato=xml`. El XML valida contra `contratos/xml/catalogos.xsd`.
"""

# ===========================================================================
# main-process-service
# ===========================================================================

ESTADOS_SOLICITUD = ["ABIERTA", "EN_PROCESO", "CERRADA"]

ESQUEMAS_PROCESO = {
    "SolicitudRespuesta": {
        "type": "object", "required": ["campania_id", "valores"],
        "description": "La respuesta se registra contra el seudónimo de quien tiene "
                       "la sesión: NO se admite empleado_id ni ningún otro "
                       "identificador de persona, y la unidad se toma del padrón de "
                       "la campaña y no de lo que mande el cliente.",
        "properties": {
            "campania_id": {"type": "string", "example": "CAMP-2026-S1"},
            "valores": {
                "type": "object",
                "additionalProperties": {"type": "integer"},
                "description": "Reactivo a valor, dentro de la escala de la versión "
                               "del instrumento.",
                "example": {"R-01": 4, "R-02": 3, "R-03": 5}}}},
    "AcuseRespuesta": {
        "type": "object",
        "properties": {
            "estado": {"type": "string",
                       "enum": ["REGISTRADA", "DUPLICADA", "SIN_CONSENTIMIENTO",
                                "CAMPANIA_CERRADA", "FUERA_DE_PADRON"],
                       "description": "No es un booleano porque las cuatro "
                                      "negativas son distintas y el portal tiene "
                                      "que explicar cada una."},
            "mensaje": {"type": "string"},
            "seudonimo_id": {"type": "string", "example": "SEUD-00042"},
            "campania_id": {"type": "string"},
            "instrumento_id": {"type": "string", "nullable": True},
            "version_instrumento": {"type": "integer", "nullable": True},
            "documento_id": {"type": "string", "nullable": True},
            "documento_pendiente": {
                "type": "boolean",
                "description": "La respuesta quedó en PostgreSQL pero el documento "
                               "espejo en MongoDB no se pudo escribir. Se informa "
                               "en lugar de fallar: la respuesta de la persona no "
                               "se pierde por una caída de la base documental."},
            "evento_id": {"type": "string", "nullable": True}}},
    "GrupoEntregas": {
        "type": "object",
        "description": "Cuenta ENTREGAS, no puntajes. Contar entregas no revela "
                       "ninguna respuesta, pero un conteo muy bajo sí revelaría "
                       "que en esa unidad respondió prácticamente una persona, y "
                       "por eso cada grupo viene marcado.",
        "properties": {
            "unidad_organizacional_id": {"type": "string"},
            "campania_id": {"type": "string"},
            "respuestas": {"type": "integer"},
            "suficiente_para_publicar": {"type": "boolean"}}},
    "ResumenEntregas": {
        "type": "object",
        "properties": {
            "total_grupos": {"type": "integer"},
            "campania_id": {"type": "string", "nullable": True},
            "umbral_aviso": {"type": "integer", "example": 5},
            "nota": {"type": "string"},
            "agregados": {"type": "array", "items": {
                "$ref": "#/components/schemas/GrupoEntregas"}}}},
    "AcuseParticipacion": {
        "type": "object",
        "description": "Comprobante de participación, no el contenido: que una "
                       "persona sepa que respondió está bien; devolverle lo que "
                       "contestó sería otra vía de salida para las respuestas.",
        "properties": {
            "campania_id": {"type": "string"},
            "instrumento_id": {"type": "string"},
            "version_instrumento": {"type": "integer"},
            "fecha": {"type": "string", "format": "date-time"},
            "reactivos_respondidos": {"type": "integer"}}},
    "ParticipacionPropia": {
        "type": "object",
        "properties": {
            "seudonimo_id": {"type": "string"},
            "total": {"type": "integer"},
            "respuestas": {"type": "array", "items": {
                "$ref": "#/components/schemas/AcuseParticipacion"}}}},
    "SolicitudApoyoAlta": {
        "type": "object", "required": ["mensaje"],
        "properties": {
            "mensaje": {"type": "string", "minLength": 20,
                        "example": "Llevo tres semanas con doble turno y no logro "
                                   "recuperarme entre jornadas."}}},
    "EntradaHistorial": {
        "type": "object",
        "properties": {
            "estado": {"type": "string", "enum": ESTADOS_SOLICITUD},
            "actor_id": {"type": "string", "nullable": True,
                         "description": "Quien MOVIÓ la solicitud, no quien la "
                                        "pidió: la rendición de cuentas de quien "
                                        "atiende es lo contrario de la privacidad "
                                        "de quien pide."},
            "fecha": {"type": "string", "format": "date-time"},
            "nota": {"type": "string"}}},
    "SolicitudApoyo": {
        "type": "object",
        "description": "El especialista que la atiende ve el mensaje y el historial "
                       "y no tiene forma de resolver quién lo escribió: eso es lo "
                       "que hace que alguien se atreva a pedir apoyo.",
        "properties": {
            "id": {"type": "string"},
            "seudonimo_id": {"type": "string"},
            "mensaje": {"type": "string"},
            "fecha": {"type": "string", "format": "date-time"},
            "estado": {"type": "string", "enum": ESTADOS_SOLICITUD},
            "fecha_actualizacion": {"type": "string", "format": "date-time",
                                    "nullable": True},
            "historial": {"type": "array", "items": {
                "$ref": "#/components/schemas/EntradaHistorial"}},
            "evento_id": {"type": "string", "nullable": True}}},
    "CambioEstadoSolicitud": {
        "type": "object", "required": ["estado"],
        "description": "Transiciones dirigidas: ABIERTA puede pasar a EN_PROCESO o "
                       "a CERRADA, EN_PROCESO solo a CERRADA, y CERRADA no vuelve "
                       "a abrirse. Reabrir borraría el rastro de que se cerró; en "
                       "su lugar se crea una solicitud nueva.",
        "properties": {
            "estado": {"type": "string", "enum": ESTADOS_SOLICITUD},
            "nota": {"type": "string"}}},
    "EventoProceso": {
        "type": "object",
        "properties": {
            "tipo": {"type": "string",
                     "enum": ["RESPUESTA_REGISTRADA", "RESPUESTA_INCOMPLETA",
                              "SOLICITUD_CREADA", "SOLICITUD_ESTADO_ACTUALIZADO",
                              "SOLICITUD_NO_ENCONTRADA"]},
            "seudonimo_id": {"type": "string",
                             "description": "Trae el valor literal SIN_SEUDONIMO "
                                            "cuando el evento no pertenece a una "
                                            "persona."},
            "correlacion_id": {"type": "string"},
            "timestamp": {"type": "string", "format": "date-time"},
            "detalle": {"type": "object",
                        "description": "Campos declarados, no abiertos: un detalle "
                                       "libre sería el hueco por el que terminaría "
                                       "viajando un empleado_id."}}},
}

RUTAS_PROCESO = {
    "/api/v1/encuestas/respuestas": {"post": {
        "tags": ["Encuestas"],
        "summary": "Registrar la respuesta a una campaña",
        "description": "Exige AUTOREPORTE_RESPONDER.\n\n"
                       "**Regla D-01:** si el cuerpo trae `empleado_id`, la "
                       "petición se rechaza completa con 400 `PRIVACIDAD_D01`. No "
                       "se limpia el campo en silencio a propósito: un cliente que "
                       "manda `empleado_id` está programado con un modelo "
                       "equivocado del sistema y conviene que lo sepa.\n\n"
                       "La escritura pasa por una función `SECURITY DEFINER` de "
                       "PostgreSQL: el rol de la aplicación no tiene INSERT sobre "
                       "el esquema `autoreporte`. La función hace cumplir RN-01 "
                       "(una respuesta por campaña), RN-02 (consentimiento "
                       "vigente), que la campaña esté abierta, y toma la unidad "
                       "del padrón.",
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/SolicitudRespuesta"},
            "examples": {
                "valida": {"summary": "Respuesta normal",
                           "value": {"campania_id": "CAMP-2026-S1",
                                     "valores": {"R-01": 4, "R-02": 3}}},
                "rechazada": {
                    "summary": "Rechazada: trae empleado_id",
                    "value": {"campania_id": "CAMP-2026-S1", "empleado_id": "EMP-7781",
                              "valores": {"R-01": 4}}}}}}},
        "responses": dict({"201": {
            "description": "Acuse del registro",
            "content": dual("AcuseRespuesta", "proceso_respuesta",
                            "  <estado>REGISTRADA</estado>")}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/encuestas/agregados/resumen": {"get": {
        "tags": ["Encuestas"],
        "summary": "Cuántas entregas hay por unidad y campaña",
        "description": "Exige AGREGADO_UNIDAD o AGREGADO_GLOBAL. Son conteos de "
                       "entrega: los puntajes solo salen del mecanismo de "
                       "agregación protegida de PostgreSQL, que aplica umbral k y "
                       "ruido de Laplace, y nunca de aquí.",
        "parameters": [
            {"name": "campania_id", "in": "query", "required": False,
             "schema": {"type": "string"}},
            {"name": "desde", "in": "query", "required": False,
             "schema": {"type": "string", "format": "date"}},
            {"name": "hasta", "in": "query", "required": False,
             "schema": {"type": "string", "format": "date"}}, PARAM_FORMATO],
        "responses": dict({"200": {
            "description": "Resumen de entregas",
            "content": dual("ResumenEntregas", "agregados_resumen",
                            "  <total_grupos>12</total_grupos>")}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/encuestas/respuestas/propias": {"get": {
        "tags": ["Encuestas"],
        "summary": "Comprobante de participación propia",
        "description": "Exige PARTICIPACION_PROPIA. Devuelve el acuse, no las "
                       "respuestas.",
        "parameters": [PARAM_FORMATO],
        "responses": dict({"200": {
            "description": "Acuses de participación",
            "content": dual("ParticipacionPropia", "participacion_propia",
                            "  <seudonimo_id>SEUD-00042</seudonimo_id>")}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/solicitudes-apoyo": {
        "post": {
            "tags": ["Apoyo"],
            "summary": "Pedir apoyo de forma seudonimizada",
            "description": "Exige APOYO_SOLICITAR. El seudónimo se resuelve en la "
                           "base a partir del usuario de la sesión y NO se acepta "
                           "del cliente: aceptarlo permitiría pedir apoyo en nombre "
                           "de otra persona o, peor, descubrir el seudónimo de "
                           "alguien probando valores.",
            "requestBody": {"required": True, "content": {"application/json": {
                "schema": {"$ref": "#/components/schemas/SolicitudApoyoAlta"}}}},
            "responses": dict({"201": {
                "description": "Solicitud creada",
                "content": dual("SolicitudApoyo", "solicitud_apoyo",
                                "  <estado>ABIERTA</estado>")}},
                **RESPUESTAS_ERROR)},
        "get": {
            "tags": ["Apoyo"],
            "summary": "Listar solicitudes para atenderlas",
            "description": "Exige APOYO_ATENDER, que es un permiso DISTINTO de "
                           "APOYO_SOLICITAR: quien puede pedir apoyo no debe poder "
                           "leer las solicitudes de los demás, y quien las atiende "
                           "no necesita poder crearlas en nombre de nadie.",
            "parameters": PARAMS_PAGINACION + [
                {"name": "estado", "in": "query", "required": False,
                 "schema": {"type": "string", "enum": ESTADOS_SOLICITUD}},
                PARAM_FORMATO],
            "responses": dict({"200": {
                "description": "Página de solicitudes",
                "content": {"application/json": {"schema": {
                    "type": "object",
                    "properties": {
                        "solicitudes": {"type": "array", "items": {
                            "$ref": "#/components/schemas/SolicitudApoyo"}},
                        "paginacion": PAGINACION_REF}}},
                    "application/xml": {"schema": {"type": "string"}}}}},
                **RESPUESTAS_ERROR)}},

    "/api/v1/solicitudes-apoyo/{id}/estado": {"patch": {
        "tags": ["Apoyo"],
        "summary": "Mover una solicitud de estado",
        "description": "Exige APOYO_ATENDER. El cambio se hace con una "
                       "actualización condicional: la condición del estado de "
                       "origen va en el WHERE, de modo que dos especialistas que "
                       "muevan la misma solicitud al mismo tiempo no puedan "
                       "aplicar los dos cambios. El segundo recibe 409.",
        "parameters": [{"name": "id", "in": "path", "required": True,
                        "schema": {"type": "string"}}],
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/CambioEstadoSolicitud"},
            "example": {"estado": "EN_PROCESO",
                        "nota": "Contactada el area de bienestar."}}}},
        "responses": dict({
            "200": {"description": "Estado actualizado",
                    "content": dual("SolicitudApoyo", "solicitud_apoyo",
                                    "  <estado>EN_PROCESO</estado>")},
            "409": {"description": "Transición no permitida desde el estado actual",
                    "content": {"application/json": {"schema": {
                        "$ref": "#/components/schemas/Error"}}}}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/eventos-proceso": {"get": {
        "tags": ["Trazabilidad"],
        "summary": "Eventos operacionales del proceso",
        "description": "Exige BITACORA_CONSULTAR. Los eventos se emiten DESPUÉS de "
                       "que la operación quedó registrada: si falla la emisión, la "
                       "operación no se pierde, porque la trazabilidad se puede "
                       "reconstruir y la respuesta de una persona no.",
        "parameters": PARAMS_PAGINACION + [
            {"name": "tipo", "in": "query", "required": False,
             "schema": {"type": "string"}},
            {"name": "correlacion_id", "in": "query", "required": False,
             "schema": {"type": "string"},
             "description": "Permite seguir una operación a través de los ocho "
                            "servicios: el mismo identificador viaja en la "
                            "cabecera X-Correlacion-Id."},
            PARAM_FORMATO],
        "responses": dict({"200": {
            "description": "Eventos",
            "content": {"application/json": {"schema": {
                "type": "object",
                "properties": {
                    "total": {"type": "integer"},
                    "eventos": {"type": "array", "items": {
                        "$ref": "#/components/schemas/EventoProceso"}},
                    "paginacion": PAGINACION_REF}}},
                "application/xml": {"schema": {"type": "string"}}}}},
            **RESPUESTAS_ERROR)}},
}

ETIQUETAS_PROCESO = [
    {"name": "Encuestas", "description": "Registro de respuestas y entregas."},
    {"name": "Apoyo", "description": "Solicitudes de apoyo seudonimizadas."},
    {"name": "Trazabilidad", "description": "Eventos operacionales del proceso."},
]

DESCRIPCION_PROCESO = """\
Proceso principal del negocio: responder una campaña y pedir apoyo.
**Integrante 2 (Ricardo Arath Sánchez Aguirre).**

**Regla D-01, que es la razón de ser del servicio:** ninguna operación
acepta `empleado_id` ni ningún otro identificador directo de persona. Las
respuestas se registran contra el seudónimo, y la correspondencia entre
seudónimo y persona no sale de PostgreSQL. Un cuerpo que traiga
`empleado_id` se rechaza completo con 400 `PRIVACIDAD_D01` en lugar de
limpiarse en silencio.

Dos bases, cada una donde le toca: la respuesta se registra en PostgreSQL a
través de una función `SECURITY DEFINER` (el rol de la aplicación no tiene
INSERT en el esquema `autoreporte`), y el documento espejo y los eventos
operacionales van a MongoDB, donde la estructura cambia de versión a
versión.

Todas las respuestas existen en JSON y en XML: `Accept: application/xml` o
`?formato=xml`. El XML valida contra `contratos/xml/proceso.xsd`.
"""

SERVICIOS = {
    "catalog-service": dict(
        titulo="catalog-service — Bienestar Nexum",
        descripcion=DESCRIPCION_CATALOGO, rutas=RUTAS_CATALOGO,
        esquemas=ESQUEMAS_CATALOGO, etiquetas=ETIQUETAS_CATALOGO, puerto=8103),
    "main-process-service": dict(
        titulo="main-process-service — Bienestar Nexum",
        descripcion=DESCRIPCION_PROCESO, rutas=RUTAS_PROCESO,
        esquemas=ESQUEMAS_PROCESO, etiquetas=ETIQUETAS_PROCESO, puerto=8104),
}

CABECERA = """\
# ARCHIVO GENERADO — no editar a mano.
#
# Lo produce contratos/generar_openapi_node.py a partir de
# comun/openapi.py, que es la misma definicion de seguridad, sobre de error
# y codigos HTTP que usan los seis microservicios en Python. Para cambiar
# este contrato se edita el generador y se vuelve a ejecutar:
#
#     python3 contratos/generar_openapi_node.py
#
"""


def main():
    for servicio, partes in SERVICIOS.items():
        contrato = construir_contrato(**partes)
        ruta = os.path.join(RAIZ, "apps", "microservicios", servicio, "openapi.yaml")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(CABECERA)
            yaml.safe_dump(contrato, f, allow_unicode=True, sort_keys=False,
                           default_flow_style=False, width=100)
        rutas = len(contrato["paths"])
        operaciones = sum(len([m for m in v if m in
                               ("get", "post", "put", "patch", "delete")])
                          for v in contrato["paths"].values())
        print(f"{servicio}: {rutas} rutas, {operaciones} operaciones, "
              f"{len(contrato['components']['schemas'])} esquemas -> openapi.yaml")


if __name__ == "__main__":
    main()
