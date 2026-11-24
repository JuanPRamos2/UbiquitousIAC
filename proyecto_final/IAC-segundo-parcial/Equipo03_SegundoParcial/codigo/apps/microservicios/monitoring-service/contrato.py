"""Contrato OpenAPI de monitoring-service.

El contrato publica tres cosas que no se ven en la firma de los endpoints
y que deciden si quien lo integre hace un panel útil o uno engañoso:

1. **Qué significa cada estado.** «degradado» devuelve 200 a propósito:
   el servicio atiende con una dependencia opcional caída. Un panel que
   pintara igual «degradado» y «sin_respuesta» haría atenderlos igual, y
   uno no es urgente y el otro sí.

2. **Que las latencias se miden desde este contenedor.** No son el tiempo
   que ve un usuario. Presentarlas como «tiempo de respuesta» haría tomar
   decisiones con un número que no mide eso.

3. **Que todo exige token.** Un panel de monitoreo suele ser lo primero
   que se abre sin autenticación «porque solo son métricas». En este
   sistema eso sería una fuga: saber que una unidad tiene datos publicados
   ya dice algo de esa unidad.
"""
from comun.openapi import RESPUESTAS_ERROR, registrar_openapi

ESQUEMAS = {
    "EstadoComponente": {
        "type": "object",
        "properties": {
            "componente": {"type": "string", "example": "queries-service"},
            "estado": {
                "type": "string",
                "enum": ["listo", "degradado", "no_listo", "sin_respuesta",
                         "desconocido"],
                "description":
                    "listo: todo responde.\n"
                    "degradado: atiende con una dependencia OPCIONAL caida; "
                    "devuelve 200 a proposito, porque el servicio SI puede "
                    "atender y sacarlo de servicio esconderia una pieza "
                    "sana.\n"
                    "no_listo: le falta una dependencia esencial y devuelve "
                    "503, pero CONTESTO: esta vivo y dice que le falta.\n"
                    "sin_respuesta: no contesto. Es otra cosa y se arregla "
                    "en otro lugar; mezclarlo con no_listo hace buscar el "
                    "problema donde no esta."},
            "http": {"type": "integer", "nullable": True,
                     "description": "Nulo cuando no hubo respuesta."},
            "latencia_ms": {"type": "number"},
            "latencia_alta": {"type": "boolean"},
            "dependencias": {
                "type": "object",
                "description": "Lo que el componente dice de SUS propias "
                               "dependencias, con cual es esencial y cual "
                               "no.",
                "additionalProperties": True},
            "degradado_por": {"type": "array", "items": {"type": "string"}},
            "falta": {"type": "array", "items": {"type": "string"},
                      "description": "Dependencias esenciales caidas."},
            "error": {"type": "string", "nullable": True},
        },
    },
}

RUTAS = {
    "/api/v1/monitoreo/componentes": {"get": {
        "tags": ["Monitoreo"],
        "summary": "El estado de cada componente, con latencia y dependencias",
        "description":
            "Sondea los componentes EN PARALELO y reporta lo que contestan. "
            "En serie, quince sondas con espera de 2.5 s son 37 segundos, y "
            "el peor caso dependeria de cuantos esten caidos: justo cuando "
            "hay que abrir el panel rapido.\n\n"
            "El estado se lee del CUERPO de cada sonda y no se deduce del "
            "codigo HTTP. La sonda devuelve 200 tanto para «listo» como "
            "para «degradado», asi que deducirlo del codigo juntaria los "
            "dos justo cuando la diferencia es lo unico que importa.\n\n"
            "Este servicio es un espejo, no una fuente de verdad: no guarda "
            "un estado propio de arriba o abajo. Si lo guardara, habria dos "
            "versiones de la salud del sistema y la gente creeria la "
            "equivocada.\n\n"
            "`veredicto` resume: operativo, degradado, con_fallas o "
            "incierto. Se calcula aqui para que no lo calcule cada pantalla "
            "a su manera.",
        "responses": dict({"200": {"description": "Estado de los componentes"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/monitoreo/componentes/{nombre}": {"get": {
        "tags": ["Monitoreo"],
        "summary": "Una sonda sola, para cuando ya se sabe a quien mirar",
        "description": "Incluye `url_sondeada`: sin eso, un «sin_respuesta» "
                       "no permite distinguir un servicio caido de una "
                       "variable de entorno mal puesta.",
        "parameters": [{"name": "nombre", "in": "path", "required": True,
                        "schema": {"type": "string"},
                        "example": "queries-service"}],
        "responses": dict({"200": {"description": "Estado del componente"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/monitoreo/dependencias": {"get": {
        "tags": ["Monitoreo"],
        "summary": "PostgreSQL, Redis y MongoDB, medidos desde aqui",
        "description":
            "Las tres sostienen a todos los componentes, asi que cuando "
            "algo falla en varios a la vez el sitio donde mirar es este y "
            "no quince sondas.\n\n"
            "MongoDB caido NO deja el sistema fuera de servicio: es "
            "OPCIONAL para los tres componentes que lo usan "
            "(documents-service, notifications-service y "
            "algorithms-service), que siguen atendiendo y se declaran "
            "degradados. El veredicto lo refleja.",
        "responses": dict({"200": {"description": "Estado de las dependencias"}},
                          **RESPUESTAS_ERROR)}},

    "/api/v1/monitoreo/contenedores": {"get": {
        "tags": ["Supervision"],
        "summary": "Cuanto lleva arriba cada proceso y si se reinicio",
        "description":
            "**Es la vista que una sonda de salud no puede dar.** Un "
            "contenedor en bucle de reinicio pasa TODAS las sondas: cada "
            "peticion le llega a un proceso recien arrancado, que contesta "
            "«vivo» con toda honestidad. El panel de componentes lo muestra "
            "en verde mientras el servicio pierde cada peticion en vuelo, "
            "cada conexion del pool y cada cache caliente.\n\n"
            "**Como se supervisa.** Comparando la `instancia` que cada "
            "servicio reporta en `/health/live`: un identificador distinto "
            "significa un proceso nuevo, es decir un reinicio. Se usa el "
            "identificador y no solo la hora porque un contenedor sin reloj "
            "sincronizado puede reportar horas que no avanzan, y entonces el "
            "conteo por hora falla justo donde hace falta.\n\n"
            "**Por que NO se lee el socket de Docker.** Seria lo directo y se "
            "decidio no hacerlo: montar `/var/run/docker.sock` dentro de un "
            "contenedor le da control del demonio de Docker, y con eso puede "
            "arrancar otro contenedor con el sistema de archivos del "
            "anfitrion montado. Equivale a root en la maquina. Un panel de "
            "monitoreo no vale eso, y ademas el proyecto tiene que funcionar "
            "tambien sin Docker, que es como corre la demostracion cuando no "
            "hay acceso a Docker Hub.\n\n"
            "El conteo vive en Redis, que recorta su ventana; cada reinicio "
            "se escribe ademas en `auditoria.bitacora` con la accion "
            "COMPONENTE_REINICIADO, que es el unico rastro que sobrevive.\n\n"
            "Un servicio que no reporte `instancia` sale como "
            "`supervision: NO_DISPONIBLE`, y no como «sin reinicios»: lo "
            "segundo seria afirmar algo que no se comprobo.",
        "responses": dict(
            {"200": {"description": "Estado de los procesos, con los "
                                    "reinicios en la ventana"}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/monitoreo/alertas": {"get": {
        "tags": ["Supervision"],
        "summary": "Las alertas activas, con su evidencia y que hacer",
        "description":
            "Ocho reglas evaluadas sobre el estado de ahora. Cada alerta "
            "lleva severidad, evidencia y accion, porque una alerta que solo "
            "dice «algo va mal» obliga a reconstruir el diagnostico cada "
            "vez.\n\n"
            "**Este servicio no manda las alertas: las publica.** Enviarlas "
            "exigiria credenciales de correo y una cola de reintentos dentro "
            "de este contenedor, y un monitor cuyo envio falla en silencio es "
            "peor que no tener monitor: nadie se enteraria y todos creerian "
            "estar cubiertos. La entrega de mensajes la hace "
            "notifications-service, que ya tiene bandeja, preferencias y "
            "registro; duplicarla aqui daria dos caminos que pueden decir "
            "cosas distintas.\n\n"
            "Dos de las reglas NO describen fallas, y se publican de todos "
            "modos:\n\n"
            "- `COMPONENTE_DEGRADADO` es un servicio atendiendo sin una "
            "dependencia opcional.\n"
            "- `PRESUPUESTO_AGOTADO` es la privacidad diferencial "
            "funcionando: la campania ya no puede publicar mas agregados de "
            "esa unidad. Se avisa porque para quien opera se ve como «ya no "
            "salen datos nuevos» y no como un error, asi que sin la alerta "
            "se busca el problema en el lugar equivocado.\n\n"
            "`REINICIOS_EN_BUCLE` es la regla que justifica la vista de "
            "contenedores: sin ella, un bucle no dispara ninguna alerta "
            "porque todas las sondas salen bien.",
        "responses": dict(
            {"200": {"description": "Alertas activas, ordenadas por "
                                    "severidad"}},
            **RESPUESTAS_ERROR)}},

    "/api/v1/monitoreo/errores": {"get": {
        "tags": ["Monitoreo"],
        "summary": "Rechazos y fallos recientes, desde la bitacora",
        "description":
            "Permiso: BITACORA_CONSULTAR o PARAMETRO_ADMIN. Aunque solo "
            "sean conteos, un conteo de rechazos por unidad ya dice en que "
            "unidad esta pasando algo.\n\n"
            "Sale de `auditoria.bitacora` y no de un contador en memoria. "
            "Un contador en memoria se pierde al reiniciar el proceso, que "
            "es justamente lo que pasa cuando algo va mal: el dato "
            "desapareceria en el momento en que hacia falta.\n\n"
            "**Un rechazo no es una falla.** RECHAZADO_PERMISO es el "
            "control funcionando y GRUPO_INSUFICIENTE es la privacidad "
            "diferencial haciendo su trabajo. Lo que hay que mirar es un "
            "cambio brusco en el volumen, no el volumen en si.",
        "parameters": [{"name": "horas", "in": "query", "required": False,
                        "schema": {"type": "integer", "default": 24,
                                   "minimum": 1, "maximum": 168}}],
        "responses": dict({"200": {"description": "Conteos por accion y resultado"}},
                          **RESPUESTAS_ERROR)}},
}

ETIQUETAS = [
    {"name": "Monitoreo",
     "description": "Estado operativo de los componentes y de las "
                    "dependencias compartidas. No expone datos."},
    {"name": "Supervision",
     "description": "Reinicios de proceso y alertas activas. Es la parte "
                    "que una sonda de salud no puede dar: un contenedor en "
                    "bucle de reinicio pasa todas las sondas."},
]


def montar(app):
    return registrar_openapi(
        app, "monitoring-service — Bienestar Nexum",
        "Salud, latencia y errores de los demas componentes.\n\n"
        "QUE RESUELVE. Cada servicio ya tenia su sonda con tres estados. Lo "
        "que no existia era quien las mire todas: para saber si el sistema "
        "estaba arriba habia que abrir trece puertos a mano, y eso "
        "significa que nadie lo hacia.\n\n"
        "DOS COSAS QUE ESTE SERVICIO NO HACE. No guarda un estado propio: "
        "pregunta y reporta. Y su propia sonda mira SOLO sus propias "
        "dependencias — si se declarara no listo porque vigila algo caido, "
        "el orquestador lo sacaria de servicio y se perderia la vista justo "
        "cuando hace falta.\n\n"
        "No expone ningun dato: ni un agregado, ni un nombre, ni un correo. "
        "Solo estado operativo, y con token.",
        rutas=RUTAS, esquemas=ESQUEMAS, etiquetas=ETIQUETAS)
