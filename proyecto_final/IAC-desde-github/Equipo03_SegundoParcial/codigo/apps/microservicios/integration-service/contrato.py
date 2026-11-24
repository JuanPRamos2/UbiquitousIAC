"""Contrato OpenAPI de integration-service.

El contrato publica dos cosas que el equipo del sistema corporativo
necesita ANTES de mandar nada, y que si no están publicadas se descubren a
base de rechazos:

1. **Qué campos no pueden entrar**, y que se rechazan en lugar de
   ignorarse. Así la extracción se limpia en el origen.

2. **Que esta integración no crea personas.** Es la regla menos obvia y la
   que más desconcierta a quien integra: un identificador cuyo seudónimo
   no existe no da de alta a nadie. El motivo está escrito en el
   contrato, no solo en el código, porque es una decisión de diseño del
   sistema y no un detalle de implementación.
"""
from comun.openapi import RESPUESTAS_ERROR, registrar_openapi

ESQUEMAS = {
    "UnidadEntrante": {
        "type": "object",
        "description": "Un renglon de estructura. Lista BLANCA de campos: "
                       "cualquier cosa de mas se reporta, y un campo de "
                       "persona hace que se rechace el archivo.",
        "required": ["unidad_organizacional_id", "nombre_unidad"],
        "properties": {
            "unidad_organizacional_id": {
                "type": "string", "pattern": "^[A-Za-z0-9_\\-\\.]{2,40}$",
                "example": "UO-OPS-CC-T1"},
            "nombre_unidad": {"type": "string", "example": "Call Center T1"},
            "unidad_padre_id": {
                "type": "string", "nullable": True,
                "description": "Nulo para la raiz. Un padre que no viene en "
                               "el archivo ni existe ya es un error: "
                               "aplicarlo dejaria una unidad huerfana, y el "
                               "alcance de todos los perfiles se calcula "
                               "recorriendo el arbol."},
            "tipo": {"type": "string",
                     "enum": ["DIRECCION", "AREA", "DEPARTAMENTO", "TURNO",
                              "EQUIPO"],
                     "default": "AREA",
                     "description": "La lista la impone la restriccion "
                                    "`unidad_organizacional_tipo_check` de "
                                    "la base, y el servicio la lee de ahi "
                                    "en lugar de guardar una copia: una "
                                    "copia escrita a mano se separa de la "
                                    "restriccion en algun momento, y la "
                                    "separacion solo se ve al insertar."},
            "plantilla_declarada": {
                "type": "integer", "minimum": 0,
                "description": "La de un padre tiene que ser la SUMA de sus "
                               "hijas. No es pulcritud: el control de "
                               "inferencia resta la plantilla del padre "
                               "menos la de las hijas conocidas para "
                               "detectar si alguien esta aislando un grupo "
                               "por debajo del umbral k. Con un arbol que no "
                               "cuadra, ese resto da cualquier cosa."},
            "activa": {"type": "boolean", "default": True},
            "descripcion": {"type": "string", "nullable": True},
        },
    },
    "IdentificadorEntrante": {
        "type": "object",
        "description": "DOS CADENAS OPACAS y nada mas. Sin nombre, sin "
                       "correo, sin numero de empleado: guardarlos junto al "
                       "seudonimo reconstruiria la identificacion completa, "
                       "que es justo lo que la seudonimizacion evita.",
        "required": ["identificador_externo", "seudonimo_id"],
        "properties": {
            "identificador_externo": {"type": "string", "maxLength": 80},
            "seudonimo_id": {
                "type": "string",
                "description": "Tiene que existir YA en esta plataforma. Si "
                               "no existe es un hallazgo, no un alta: ver la "
                               "descripcion del endpoint."},
            "activo": {"type": "boolean", "default": True},
        },
    },
    "Hallazgo": {
        "type": "object",
        "description": "Por que se rechazo, renglon por renglon y campo por "
                       "campo. Quien tiene que arreglar el archivo no es "
                       "quien opera esta plataforma: si el error no dice el "
                       "renglon y el campo, el arreglo pasa por una cadena "
                       "de correos.",
        "properties": {
            "renglon": {"type": "integer", "nullable": True,
                        "description": "Nulo en los hallazgos del archivo "
                                       "como conjunto, como un ciclo o una "
                                       "jerarquia que no cuadra."},
            "campo": {"type": "string", "nullable": True},
            "codigo": {
                "type": "string",
                "enum": ["RENGLON_INVALIDO", "CAMPO_DE_PERSONA",
                         "CAMPO_NO_ESPERADO", "IDENTIFICADOR_INVALIDO",
                         "IDENTIFICADOR_REPETIDO", "CAMPO_OBLIGATORIO",
                         "TIPO_INVALIDO", "NO_ES_ENTERO",
                         "PLANTILLA_NEGATIVA", "PADRE_INEXISTENTE",
                         "CICLO", "JERARQUIA_NO_CUADRA",
                         "SEUDONIMO_NO_EXISTE", "APLICACION_FALLIDA"]},
            "severidad": {
                "type": "string", "enum": ["ERROR", "ADVERTENCIA"],
                "description": "ERROR impide aplicar; ADVERTENCIA no. La "
                               "distincion existe porque sin ella todo se "
                               "vuelve error y la integracion se vuelve "
                               "inusable, o todo se vuelve advertencia y "
                               "deja de proteger."},
            "detalle": {"type": "string"},
        },
    },
}

_CUERPO_MODO = {
    "fuente_id": {"type": "string", "example": "FC-RH-CORPORATIVO"},
    "modo": {"type": "string", "enum": ["VALIDAR", "APLICAR"],
             "default": "VALIDAR",
             "description": "VALIDAR no escribe nada: contesta si el "
                            "archivo pasaria. Sin este modo, la unica forma "
                            "de saber si un archivo sirve seria aplicarlo."},
}

RUTAS = {
    "/api/v1/integracion/estructura": {"post": {
        "tags": ["Integracion"],
        "summary": "Importa el arbol organizacional. Todo o nada",
        "description":
            "Acepta JSON y XML.\n\n"
            "**Aplicar es todo o nada**, y es la decision OPUESTA a la de "
            "sync-service, a proposito: un lote de autoreportes a medio "
            "aplicar son respuestas guardadas, que es un resultado util; un "
            "arbol organizacional a medio aplicar son unidades huerfanas, y "
            "el alcance de todos los perfiles se calcula recorriendo ese "
            "arbol. Un arbol roto significa gente viendo datos de areas que "
            "no le tocan, o no viendo los suyos.\n\n"
            "**La jerarquia tiene que cuadrar**: la plantilla de un padre "
            "debe ser la suma de sus hijas. Se valida en la base "
            "(`integracion.fn_validar_arbol_propuesto`) y se vuelve a "
            "comprobar DESPUES de aplicar, porque el arbol final incluye "
            "unidades que ya estaban y que el archivo no toco.\n\n"
            "**Los campos de persona se rechazan, no se ignoran.** "
            "Ver `/campos-rechazados`.\n\n"
            "**En XML se valida contra `integracion.xsd` ANTES de leer el "
            "contenido**, y el esquema se publica en `/esquema.xsd`. El "
            "esquema declara lo PERMITIDO —los renglones son `xs:all` "
            "cerrado, sin `xs:any`— asi que un elemento no previsto hace "
            "fallar la validacion aunque no este en ninguna lista negra. Es "
            "la defensa que cubre lo que una enumeracion no anticipo. La "
            "respuesta trae `validacion_xsd`: VALIDADO, NO_APLICA (el "
            "cuerpo venia en JSON) o NO_DISPONIBLE (el esquema no se pudo "
            "cargar en este despliegue; no se finge que se valido).\n\n"
            "Lo que el esquema NO puede comprobar es que la plantilla de un "
            "padre sea la suma de sus hijas: eso no se expresa en XSD y lo "
            "hace `integracion.fn_validar_arbol_propuesto` en la base. "
            "Pasar el esquema no significa que el arbol cuadre.\n\n"
            "Veredictos: `SOLO_VALIDADA` (paso y no se escribio nada), "
            "`ACEPTADA` (se aplico), `RECHAZADA` (422, con los hallazgos). "
            "`SOLO_VALIDADA` se distingue de `ACEPTADA` a proposito: "
            "confundirlas haria creer que el arbol ya se actualizo.\n\n"
            "Permiso: IMPORTACION_APLICAR o UNIDAD_ADMIN.",
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"type": "object",
                       "required": ["fuente_id", "unidades"],
                       "properties": dict(_CUERPO_MODO, unidades={
                           "type": "array",
                           "items": {"$ref": "#/components/schemas/UnidadEntrante"}})}}}},
        "responses": dict(
            {"200": {"description": "ACEPTADA o SOLO_VALIDADA, con el "
                                    "informe"},
             "422": {"description": "RECHAZADA, con los hallazgos renglon "
                                    "por renglon"}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/integracion/identificadores": {"post": {
        "tags": ["Integracion"],
        "summary": "Sincroniza la correspondencia externo <-> seudonimo",
        "description":
            "**Esta integracion NO crea personas.** Es la regla menos obvia "
            "del servicio y la razon es de diseno del sistema, no de "
            "implementacion: una persona creada por una importacion no "
            "tendria registro de consentimiento, y el consentimiento es lo "
            "que habilita que su respuesta cuente (RN-02). Una persona "
            "creada por aqui podria empezar a aparecer en agregados sin "
            "haber aceptado nada.\n\n"
            "Por eso un `seudonimo_id` que no existe produce el hallazgo "
            "`SEUDONIMO_NO_EXISTE` y no un alta. El alta de una persona pasa "
            "por el flujo de consentimiento.\n\n"
            "La tabla guarda dos cadenas opacas y nada mas, y nunca se une "
            "con `consentimiento.seudonimo`: juntar el identificador "
            "corporativo, el seudonimo y la persona en un solo lugar "
            "reconstruiria la identificacion completa.\n\n"
            "Un seudonimo no puede corresponder a dos identificadores de la "
            "misma fuente: la misma persona entraria dos veces y contaria "
            "doble en cualquier conteo.\n\n"
            "Permiso: IMPORTACION_APLICAR o USUARIO_ADMIN.",
        "requestBody": {"required": True, "content": {"application/json": {
            "schema": {"type": "object",
                       "required": ["fuente_id", "identificadores"],
                       "properties": dict(_CUERPO_MODO, identificadores={
                           "type": "array",
                           "items": {"$ref": "#/components/schemas/IdentificadorEntrante"}})}}}},
        "responses": dict(
            {"200": {"description": "ACEPTADA o SOLO_VALIDADA"},
             "422": {"description": "RECHAZADA, con los hallazgos"}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/integracion/fuentes": {"get": {
        "tags": ["Integracion"],
        "summary": "Las fuentes registradas y que puede mandar cada una",
        "description":
            "Incluye las registradas y NO autorizadas, con su motivo "
            "escrito. Estan ahi a proposito: una fuente ausente de la lista "
            "parece un olvido, y una presente con el motivo es una decision "
            "que alguien tomo.\n\n"
            "Una fuente no registrada no puede integrar. Lo normal es "
            "aceptar de cualquiera que traiga un token valido, y entonces "
            "cualquier componente con credenciales de la organizacion puede "
            "reescribir el arbol organizacional.",
        "responses": dict({"200": {"description": "Fuentes registradas"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/integracion/esquema.xsd": {"get": {
        "tags": ["Integracion"],
        "summary": "El XSD contra el que se valida, servido por el servicio",
        "description":
            "Para que el equipo del sistema corporativo valide ANTES de "
            "mandar, en lugar de descubrir los problemas a base de "
            "rechazos.\n\n"
            "Lo sirve el propio servicio para que el esquema publicado sea "
            "EL MISMO contra el que se valida. Mandarlo por correo crearia "
            "dos copias que se separan, y entonces un archivo correcto "
            "segun la copia vieja se rechaza sin explicacion entendible.",
        "responses": dict({"200": {"description": "integracion.xsd",
                                   "content": {"application/xml": {}}}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/integracion/campos-rechazados": {"get": {
        "tags": ["Integracion"],
        "summary": "Los campos que no pueden entrar, publicados",
        "description":
            "Esta en el contrato para que el equipo del sistema corporativo "
            "pueda limpiar su extraccion ANTES de mandarla, en lugar de "
            "descubrirlo a base de rechazos.\n\n"
            "La coincidencia es por CONTENIDO del nombre del campo, sin "
            "acentos y en minusculas: 'nombre' rechaza tambien "
            "'nombre_completo' y 'primer_nombre'. Una comparacion exacta "
            "dejaria pasar casi todos los nombres que de verdad usa un "
            "sistema corporativo.",
        "responses": dict({"200": {"description": "La lista y el motivo"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/integracion/ingestas": {"get": {
        "tags": ["Historial"],
        "summary": "Historial de integraciones, con las rechazadas",
        "description":
            "Las rechazadas son la mitad del valor de tener una puerta: un "
            "intento de meter campos de persona que no quedara registrado no "
            "habria existido nunca.",
        "responses": dict({"200": {"description": "Ultimas 50 ingestas"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/integracion/ingestas/{ingesta_id}": {"get": {
        "tags": ["Historial"],
        "summary": "Una ingesta con sus hallazgos",
        "parameters": [{"name": "ingesta_id", "in": "path", "required": True,
                        "schema": {"type": "integer"}}],
        "responses": dict({"200": {"description": "La ingesta y su detalle"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Integracion",
     "description": "La puerta: estructura, identificadores y sus reglas."},
    {"name": "Historial",
     "description": "Lo que entro y lo que se rechazo."},
]


def montar(app):
    return registrar_openapi(
        app, "integration-service — Bienestar Nexum",
        "Integracion controlada con el sistema corporativo.\n\n"
        "Conectar un sistema corporativo de recursos humanos a una "
        "plataforma de bienestar es el momento donde un proyecto asi se "
        "puede romper, y no por un error tecnico: el sistema de origen "
        "TIENE los nombres, los puestos, los sueldos y las fechas de "
        "nacimiento, y la via de integracion es por donde entrarian. Casi "
        "siempre entran sin que nadie lo decida, porque el origen manda su "
        "registro completo y el destino guarda «lo que venga, por si "
        "acaso».\n\n"
        "Asi que esto no es un espejo del padron corporativo: es una puerta "
        "estrecha, con registro de lo que paso y de lo que se rechazo. "
        "Admite estructura organizacional e identificadores "
        "seudonimizados, y nada mas. No crea personas.",
        rutas=RUTAS, esquemas=ESQUEMAS, etiquetas=ETIQUETAS)
