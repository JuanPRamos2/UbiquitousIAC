"""
Pruebas de catalog-service y main-process-service (Integrante 2).

Estos dos microservicios están escritos en Node, así que no se pueden
importar como los de Python: se levantan de verdad, en un puerto libre, y
se les habla por HTTP.

Que la prueba sea así no es un inconveniente, es el punto. Lo que se
comprueba aquí no se podría comprobar con un mock:

  * un token emitido por auth-service (Python, PyJWT) se valida en
    catalog-service (Node, jsonwebtoken) — mismo secreto, mismo algoritmo;
  * los dos leen la MISMA sesión en Redis, de modo que un cierre de sesión
    revoca en todos los componentes;
  * el XML que produce el serializador de Node valida contra el MISMO XSD
    que el de Python;
  * los permisos salen de usuarios.perfil_permiso en los dos lenguajes.

Si falta Node o faltan las dependencias, las pruebas se omiten con un
motivo en lugar de fallar: el resto de la suite no depende de esto.
"""
import json
import os

import pytest
from conftest import http
from lxml import etree

XSD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "contratos", "xml")


def validar(bytes_xml, nombre_xsd):
    esq = etree.XMLSchema(etree.parse(os.path.join(XSD, nombre_xsd)))
    doc = etree.fromstring(bytes_xml)
    if not esq.validate(doc):
        pytest.fail(f"La respuesta de Node no cumple {nombre_xsd}:\n" +
                    "\n".join(str(e) for e in esq.error_log))
    return doc


# =========================================================================
# catalog-service
# =========================================================================

def test_sondas_y_contrato(catalogo_node):
    codigo, _, _ = http("GET", catalogo_node, "/health/live")
    assert codigo == 200
    codigo, _, cuerpo = http("GET", catalogo_node, "/health/ready")
    assert codigo == 200, cuerpo
    salud = json.loads(cuerpo)
    assert salud["dependencias"]["postgresql"]["ok"] is True
    assert salud["dependencias"]["redis"]["ok"] is True

    codigo, _, cuerpo = http("GET", catalogo_node, "/openapi.json")
    assert codigo == 200
    contrato = json.loads(cuerpo)
    # El contrato lo genera el MISMO modulo que usan los servicios en
    # Python, asi que tiene que traer las siete respuestas de error comunes.
    assert len(contrato["components"]["responses"]) == 7
    assert contrato["components"]["securitySchemes"]["bearerAuth"]
    assert http("GET", catalogo_node, "/docs")[0] == 200


def test_sin_token_no_se_lee_ni_el_catalogo(catalogo_node):
    """Leer el catálogo también exige token: revela la estructura de la empresa."""
    codigo, _, cuerpo = http("GET", catalogo_node, "/api/v1/catalogos/unidades")
    assert codigo == 401
    assert json.loads(cuerpo)["error"]["codigo"] == "TOKEN_AUSENTE"


def test_un_token_de_python_sirve_en_node(catalogo_node, token_admin):
    """La prueba que sostiene la afirmación de autenticación compartida.

    El token lo firmó auth-service con PyJWT; lo valida catalog-service con
    jsonwebtoken, y la sesión la lee de la misma instancia de Redis.
    """
    codigo, _, cuerpo = http("GET", catalogo_node,
                             "/api/v1/catalogos/unidades?limit=3", token_admin)
    assert codigo == 200, cuerpo
    datos = json.loads(cuerpo)
    assert len(datos["unidades"]) == 3
    assert datos["paginacion"]["total"] >= 16


def test_un_token_inventado_se_rechaza(catalogo_node):
    codigo, _, cuerpo = http("GET", catalogo_node, "/api/v1/catalogos/unidades",
                             token="esto.no.es.un.token")
    assert codigo == 401
    assert json.loads(cuerpo)["error"]["codigo"] == "TOKEN_INVALIDO"


def test_cerrar_sesion_en_python_revoca_en_node(catalogo_node, auth):
    """Un logout en auth-service deja fuera de catalog-service.

    Es la consecuencia práctica de compartir Redis, y es la razón de que la
    revocación no viva en la memoria de cada proceso.
    """
    from conftest import cab, iniciar_sesion
    token = iniciar_sesion(auth, "carlos.ramirez@nexum.com.mx")
    assert http("GET", catalogo_node, "/api/v1/catalogos/unidades?limit=1",
                token)[0] == 200

    assert auth.post("/api/v1/auth/logout", headers=cab(token)).status_code == 200

    codigo, _, cuerpo = http("GET", catalogo_node,
                             "/api/v1/catalogos/unidades?limit=1", token)
    assert codigo == 401
    assert json.loads(cuerpo)["error"]["codigo"] == "SESION_REVOCADA"


def test_el_xml_de_node_cumple_el_mismo_xsd(catalogo_node, token_admin):
    """Un solo esquema describe las respuestas de los dos lenguajes."""
    casos = [
        ("/api/v1/catalogos/unidades?limit=2", "unidades_respuesta"),
        ("/api/v1/catalogos/instrumentos", "instrumentos_respuesta"),
        ("/api/v1/catalogos/reactivos?limit=3", "reactivos_respuesta"),
        ("/api/v1/catalogos/campanias", "campanias_respuesta"),
        ("/api/v1/catalogos/dimensiones", "dimensiones_respuesta"),
        ("/api/v1/catalogos/fuentes", "fuentes_respuesta"),
        ("/api/v1/catalogos/unidades/UO-CC-TURNO-B", "unidad_respuesta"),
        ("/api/v1/catalogos/campanias/CAMP-2026-S1", "campania_respuesta"),
        ("/api/v1/catalogos/instrumentos/INST-BIENESTAR/versiones",
         "versiones_respuesta"),
        ("/api/v1/catalogos/instrumentos/INST-BIENESTAR/versiones/1/reactivos",
         "reactivos_version_respuesta"),
    ]
    for ruta, raiz_esperada in casos:
        codigo, cabeceras, cuerpo = http("GET", catalogo_node, ruta, token_admin,
                                         xml=True)
        assert codigo == 200, (ruta, cuerpo)
        assert "xml" in cabeceras["Content-Type"]
        doc = validar(cuerpo, "catalogos.xsd")
        assert etree.QName(doc).localname == raiz_esperada, ruta


def test_una_fecha_de_calendario_no_lleva_hora(catalogo_node, token_admin):
    """fecha_inicio es un día, no un instante.

    La biblioteca pg convierte DATE a un objeto Date de JavaScript, que se
    serializa como 2026-08-07T00:00:00.000Z. Eso rompe el contrato
    (xs:date) y, peor, un cliente al poniente de UTC lee ese instante como
    el 6 de agosto: la fecha de cierre de una campaña se corre un día.
    """
    codigo, _, cuerpo = http("GET", catalogo_node,
                             "/api/v1/catalogos/campanias/CAMP-2026-S1", token_admin)
    assert codigo == 200
    campania = json.loads(cuerpo)["campania"]
    assert campania["fecha_inicio"].count("-") == 2
    assert "T" not in campania["fecha_inicio"], campania["fecha_inicio"]
    assert "T" not in campania["fecha_fin"], campania["fecha_fin"]


def test_el_formato_tambien_se_pide_por_parametro(catalogo_node, token_admin):
    """?formato=xml, para poder demostrarlo desde la barra del navegador."""
    codigo, cabeceras, cuerpo = http(
        "GET", catalogo_node, "/api/v1/catalogos/dimensiones?formato=xml",
        token_admin)
    assert codigo == 200
    assert "xml" in cabeceras["Content-Type"]
    validar(cuerpo, "catalogos.xsd")


def test_la_cache_de_node_informa_su_origen(catalogo_node, token_admin):
    primera = http("GET", catalogo_node,
                   "/api/v1/catalogos/reactivos?limit=5", token_admin)
    segunda = http("GET", catalogo_node,
                   "/api/v1/catalogos/reactivos?limit=5", token_admin)
    assert primera[0] == segunda[0] == 200
    assert segunda[1].get("X-Cache") == "ACIERTO", segunda[1]
    assert json.loads(segunda[2])["desde_cache"] is True
    # Y los datos no cambian al salir de la cache.
    assert json.loads(primera[2])["reactivos"] == json.loads(segunda[2])["reactivos"]


def test_el_colaborador_lee_pero_no_escribe(catalogo_node, token_colaborador):
    """Los permisos salen de la base también en Node.

    El colaborador necesita leer el catálogo (son los reactivos que va a
    responder) y no debe poder tocar el árbol organizacional.
    """
    assert http("GET", catalogo_node, "/api/v1/catalogos/reactivos?limit=2",
                token_colaborador)[0] == 200

    codigo, _, cuerpo = http("POST", catalogo_node, "/api/v1/catalogos/unidades",
                             token_colaborador,
                             cuerpo={"unidad_organizacional_id": "UO-PIRATA",
                                     "nombre": "Unidad creada sin permiso"})
    assert codigo == 403
    assert json.loads(cuerpo)["error"]["codigo"] == "SIN_PERMISO"


def test_la_baja_es_logica_y_devuelve_la_entidad(catalogo_node, token_admin):
    """DELETE no borra: marca inactivo y devuelve la entidad.

    Se crea una unidad de prueba, se le da de baja y se comprueba que
    SIGUE EXISTIENDO con activa=false. Un borrado real rompería las llaves
    foráneas de las respuestas ya registradas.
    """
    unidad = {"unidad_organizacional_id": "UO-PRUEBA-BAJA",
              "nombre": "Unidad de prueba de baja logica",
              "tipo": "EQUIPO", "unidad_padre_id": "UO-OPERACIONES",
              "plantilla_declarada": 7}
    # Idempotente: si quedo de una corrida anterior, se reutiliza.
    codigo, _, _ = http("POST", catalogo_node, "/api/v1/catalogos/unidades",
                        token_admin, cuerpo=unidad)
    assert codigo in (201, 409, 422), codigo

    codigo, _, cuerpo = http("DELETE", catalogo_node,
                             f"/api/v1/catalogos/unidades/{unidad['unidad_organizacional_id']}",
                             token_admin)
    assert codigo == 200, cuerpo
    assert json.loads(cuerpo)["unidad"]["activa"] is False

    # Y sigue consultable: no desaparecio.
    codigo, _, cuerpo = http("GET", catalogo_node,
                             f"/api/v1/catalogos/unidades/{unidad['unidad_organizacional_id']}",
                             token_admin)
    assert codigo == 200
    assert json.loads(cuerpo)["unidad"]["activa"] is False


def test_el_error_de_node_tiene_la_misma_forma_que_el_de_python(catalogo_node,
                                                                token_admin):
    """Un cliente escribe su manejo de errores UNA vez para los ocho servicios."""
    codigo, _, cuerpo = http("GET", catalogo_node,
                             "/api/v1/catalogos/unidades/UO-NO-EXISTE", token_admin)
    assert codigo == 404
    error = json.loads(cuerpo)["error"]
    assert set(error) >= {"codigo", "mensaje", "detalles", "correlacion_id"}
    assert error["codigo"] == "NO_ENCONTRADO"
    assert error["correlacion_id"]

    # Y en XML valida contra comun.xsd, igual que el de los otros servicios.
    codigo, _, cuerpo = http("GET", catalogo_node,
                             "/api/v1/catalogos/unidades/UO-NO-EXISTE", token_admin,
                             xml=True)
    assert codigo == 404
    validar(cuerpo, "comun.xsd")


def test_la_correlacion_viaja_entre_servicios(catalogo_node, token_admin):
    """El mismo identificador permite seguir una operación por los ocho."""
    codigo, cabeceras, _ = http("GET", catalogo_node,
                                "/api/v1/catalogos/dimensiones", token_admin)
    assert codigo == 200
    assert cabeceras.get("X-Correlacion-Id")
    assert cabeceras.get("X-Servicio") == "catalog-service"


# =========================================================================
# main-process-service
# =========================================================================

def test_proceso_responde_su_sonda_y_su_contrato(proceso_node):
    assert http("GET", proceso_node, "/health/live")[0] == 200
    codigo, _, cuerpo = http("GET", proceso_node, "/openapi.json")
    assert codigo == 200
    contrato = json.loads(cuerpo)
    assert "/api/v1/encuestas/respuestas" in contrato["paths"]
    assert len(contrato["components"]["responses"]) == 7


def test_la_regla_d01_rechaza_el_identificador_de_empleado(proceso_node,
                                                           token_colaborador):
    """La regla que define al servicio.

    Si el cuerpo trae empleado_id, la petición se rechaza COMPLETA. No se
    limpia el campo en silencio: un cliente que manda empleado_id está
    programado con un modelo equivocado del sistema y conviene que lo sepa.

    Se comprueba antes de tocar cualquier base, así que esta prueba pasa
    incluso donde MongoDB no está disponible — y eso también es parte del
    diseño: la verificación de privacidad no depende de que la base
    responda.
    """
    codigo, _, cuerpo = http("POST", proceso_node,
                             "/api/v1/encuestas/respuestas", token_colaborador,
                             cuerpo={"campania_id": "CAMP-2026-S1",
                                     "empleado_id": "EMP-7781",
                                     "valores": {"R-01": 4}})
    assert codigo == 400, cuerpo
    error = json.loads(cuerpo)["error"]
    assert error["codigo"] == "PRIVACIDAD_D01"
    assert error["detalles"][0]["campo"] == "empleado_id"


def test_el_proceso_tambien_exige_token(proceso_node):
    codigo, _, cuerpo = http("POST", proceso_node, "/api/v1/encuestas/respuestas",
                             cuerpo={"campania_id": "CAMP-2026-S1"})
    assert codigo == 401
    assert json.loads(cuerpo)["error"]["codigo"] == "TOKEN_AUSENTE"


def test_pedir_apoyo_y_atenderlo_son_permisos_distintos(proceso_node,
                                                        token_colaborador,
                                                        token_especialista):
    """Quien puede pedir apoyo no debe poder leer las solicitudes de los demás.

    Es una separación deliberada: si el mismo permiso sirviera para las dos
    cosas, cualquiera que pudiera pedir apoyo podría leer lo que escribieron
    sus compañeros, y nadie volvería a escribir nada.
    """
    codigo, _, cuerpo = http("GET", proceso_node, "/api/v1/solicitudes-apoyo",
                             token_colaborador)
    assert codigo == 403, cuerpo
    assert json.loads(cuerpo)["error"]["codigo"] == "SIN_PERMISO"

    # El especialista si puede listarlas (200 con MongoDB arriba, 503 sin el:
    # en ninguno de los dos casos es un 403, que es lo que se prueba aqui).
    codigo, _, _ = http("GET", proceso_node, "/api/v1/solicitudes-apoyo",
                        token_especialista)
    assert codigo != 403


def test_el_colaborador_no_lee_los_eventos_de_proceso(proceso_node,
                                                      token_colaborador):
    codigo, _, cuerpo = http("GET", proceso_node, "/api/v1/eventos-proceso",
                             token_colaborador)
    assert codigo == 403
    assert json.loads(cuerpo)["error"]["codigo"] == "SIN_PERMISO"


def test_la_sonda_de_listo_reporta_mongodb_como_dependencia(proceso_node):
    """Sin MongoDB el servicio NO se declara listo.

    Es lo correcto: main-process-service escribe el documento espejo y los
    eventos operacionales en MongoDB, así que declararse listo sin esa base
    sería mentirle al orquestador, que entonces le mandaría tráfico.
    """
    codigo, _, cuerpo = http("GET", proceso_node, "/health/ready")
    salud = json.loads(cuerpo)
    assert "mongodb" in salud["dependencias"]
    if codigo == 200:
        assert salud["dependencias"]["mongodb"]["ok"] is True
    else:
        assert codigo == 503
        assert salud["dependencias"]["mongodb"]["ok"] is False


# =========================================================================
# Las constantes de Node contra la base de datos
# =========================================================================

def test_los_codigos_de_node_existen_en_la_base():
    """Las constantes de comun-node tienen que existir en usuarios.permiso.

    Esta prueba existe por un error concreto: la migración 004 agregó
    UNIDAD_ADMIN, APOYO_SOLICITAR y APOYO_ATENDER a la base y nadie los
    agregó al módulo de constantes de Node. El resultado era
    `autorizar(undefined)`, es decir un 403 para todo el mundo en la ruta de
    solicitudes de apoyo —incluido el perfil que sí tenía el permiso— y
    nada en los registros que apuntara a la causa.

    Al revés también importa: una constante que ya no existe en la base
    deja una ruta autorizando contra un permiso que nadie puede tener.
    """
    import shutil
    import subprocess

    import psycopg2

    if not shutil.which("node"):
        pytest.skip("node no esta instalado en este ambiente")

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    modulo = os.path.join(raiz, "apps", "microservicios", "comun-node", "src",
                          "catalogos-auditoria.js")
    guion = (f"import('file://{modulo}').then(m => "
             "console.log(JSON.stringify({"
             "permisos: Object.keys(m.PERMISOS), "
             "acciones: Object.keys(m.ACCIONES), "
             "perfiles: Object.keys(m.PERFILES)})))")
    salida = subprocess.run(["node", "-e", guion], capture_output=True,
                            text=True, timeout=30)
    assert salida.returncode == 0, salida.stderr
    constantes = json.loads(salida.stdout)

    cn = psycopg2.connect(host=os.environ["PG_HOST"], dbname=os.environ["PG_BASE"],
                          user=os.environ["PG_USUARIO"],
                          password=os.environ["PG_CLAVE"])
    with cn, cn.cursor() as cur:
        cur.execute("SELECT codigo FROM usuarios.permiso")
        permisos_bd = {f[0] for f in cur.fetchall()}
        cur.execute("SELECT codigo FROM auditoria.tipo_accion")
        acciones_bd = {f[0] for f in cur.fetchall()}
        cur.execute("SELECT codigo FROM usuarios.perfil")
        perfiles_bd = {f[0] for f in cur.fetchall()}
    cn.close()

    # Los PERMISOS sí se comparan en las dos direcciones. Una constante que
    # no existe en la base deja una ruta autorizando contra un permiso que
    # nadie puede tener; un permiso de la base que falta aquí es el error
    # que motivó esta prueba.
    assert set(constantes["permisos"]) == permisos_bd, (
        "los permisos de Node y los de la base no coinciden.\n"
        f"  solo en Node: {sorted(set(constantes['permisos']) - permisos_bd)}\n"
        f"  solo en la base: {sorted(permisos_bd - set(constantes['permisos']))}")

    # Los PERFILES solo se comparan en una dirección, y es a propósito: el
    # control de acceso es dirigido por datos, así que crear un perfil nuevo
    # desde la pantalla de administración es una operación normal y NO debe
    # romper esta prueba. Lo que no puede pasar es lo contrario: que el
    # código nombre un perfil que no existe en la base.
    assert set(constantes["perfiles"]) <= perfiles_bd, (
        f"perfiles que Node nombra y la base no tiene: "
        f"{sorted(set(constantes['perfiles']) - perfiles_bd)}")
    # Las acciones de Node son un subconjunto: la base declara tambien las
    # que emiten el sistema web y los servicios en Python.
    assert set(constantes["acciones"]) <= acciones_bd, (
        f"acciones que Node emite y la base no declara: "
        f"{sorted(set(constantes['acciones']) - acciones_bd)}")


# =========================================================================
# Cuerpo de la peticion en XML
# =========================================================================
# La aplicacion de escritorio del proyecto consume EXCLUSIVAMENTE XML. Hasta
# ahora los dos servicios de Node leian el cuerpo con express.json(), asi que
# una peticion en XML llegaba con el cuerpo vacio y el servicio respondia 422
# por campos obligatorios que el cliente SI habia mandado. Estas pruebas
# existen porque ese error es silencioso: el cliente ve un 422 con un mensaje
# correcto y nunca sospecha del formato.

ENVOLTURA = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<{raiz} xmlns="http://nexum.com.mx/bienestar/v1"'
             ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
             '{cuerpo}</{raiz}>')


def test_escribir_una_unidad_con_cuerpo_en_xml(catalogo_node, token_admin):
    """POST con Content-Type application/xml crea la unidad igual que con JSON."""
    xml = ENVOLTURA.format(raiz="Unidad", cuerpo=(
        "<unidad_organizacional_id>UO-PRUEBA-XML</unidad_organizacional_id>"
        "<nombre>Unidad creada desde XML</nombre>"
        "<tipo>EQUIPO</tipo>"
        "<unidad_padre_id>UO-OPERACIONES</unidad_padre_id>"
        "<plantilla_declarada>9</plantilla_declarada>"))
    codigo, _, cuerpo = http("POST", catalogo_node, "/api/v1/catalogos/unidades",
                             token_admin, cuerpo_xml=xml)
    # 201 la primera vez; 409 si quedo de una corrida anterior. Lo que NO
    # puede pasar es un 422: eso significaria que el cuerpo llego vacio.
    assert codigo in (201, 409), cuerpo
    if codigo == 201:
        assert json.loads(cuerpo)["unidad"]["nombre"] == "Unidad creada desde XML"

    codigo, _, cuerpo = http("GET", catalogo_node,
                             "/api/v1/catalogos/unidades/UO-PRUEBA-XML", token_admin)
    assert codigo == 200, cuerpo
    assert json.loads(cuerpo)["unidad"]["nombre"] == "Unidad creada desde XML"


def test_el_numero_en_xml_no_se_adivina_pero_si_se_valida(catalogo_node,
                                                          token_admin):
    """El lector entrega cadenas; la validacion del servicio sigue siendo la misma.

    `plantilla_declarada` llega como "no-es-numero" y el servicio responde
    422, no 500: el cuerpo se leyo bien y la regla de validacion actuo.
    """
    xml = ENVOLTURA.format(raiz="Unidad", cuerpo=(
        "<unidad_organizacional_id>UO-PRUEBA-XML-MALA</unidad_organizacional_id>"
        "<nombre>Unidad con plantilla invalida</nombre>"
        "<tipo>EQUIPO</tipo>"
        "<plantilla_declarada>no-es-numero</plantilla_declarada>"))
    codigo, _, cuerpo = http("POST", catalogo_node, "/api/v1/catalogos/unidades",
                             token_admin, cuerpo_xml=xml)
    assert codigo == 422, cuerpo
    assert json.loads(cuerpo)["error"]["codigo"] == "VALIDACION"


def test_un_xml_mal_formado_responde_400_y_no_500(catalogo_node, token_admin):
    codigo, _, cuerpo = http("POST", catalogo_node, "/api/v1/catalogos/unidades",
                             token_admin, cuerpo_xml="<Unidad><nombre>sin cerrar")
    assert codigo == 400, cuerpo
    assert json.loads(cuerpo)["error"]["codigo"] == "XML_MAL_FORMADO"


def test_el_json_sigue_funcionando_despues_del_lector_de_xml(catalogo_node,
                                                             token_admin):
    """El lector de XML se monta antes del de JSON y no debe estorbarle."""
    codigo, _, cuerpo = http("POST", catalogo_node, "/api/v1/catalogos/unidades",
                             token_admin,
                             cuerpo={"unidad_organizacional_id": "UO-PRUEBA-JSON",
                                     "nombre": "Unidad creada desde JSON",
                                     "tipo": "EQUIPO",
                                     "unidad_padre_id": "UO-OPERACIONES",
                                     "plantilla_declarada": 4})
    assert codigo in (201, 409), cuerpo


def test_cambiar_el_estado_de_una_solicitud_desde_xml(proceso_node, token_especialista):
    """El PATCH que hace la aplicacion de escritorio, con el cuerpo en XML.

    Es la operacion de escritura del jefe de unidad, y la que convierte
    "la app de escritorio consume solo XML" en algo cierto tambien para las
    escrituras y no nada mas para las lecturas.

    La prueba no necesita que MongoDB este arriba, y eso es a proposito. Se
    manda el PATCH a un identificador que no existe y se mira QUE error
    contesta:

      * si el cuerpo XML no se hubiera leido, `estado` llegaria vacio y la
        primera validacion del servicio responderia ESTADO_INVALIDO;
      * si el cuerpo si se leyo, esa validacion pasa y el servicio avanza a
        buscar la solicitud, donde ya depende del almacen.

    Asi la prueba distingue "no se leyo el XML" de "no hay MongoDB", que es
    justo lo que una prueba que solo mirara el codigo HTTP confundiria.
    """
    cambio = ENVOLTURA.format(raiz="CambioEstadoSolicitud", cuerpo=(
        "<estado>EN_PROCESO</estado>"
        "<nota>Atendida desde la aplicacion de escritorio, en XML</nota>"))
    codigo, _, cuerpo = http("PATCH", proceso_node,
                             "/api/v1/solicitudes-apoyo/no-existe-este-id/estado",
                             token_especialista, cuerpo_xml=cambio)
    error = json.loads(cuerpo).get("error", {})
    assert error.get("codigo") != "ESTADO_INVALIDO", (
        "El servicio no leyo el estado del cuerpo XML: el lector de XML no "
        f"esta actuando. Respuesta: {cuerpo}")
    # 400 significaria que el servicio rechazo el cuerpo; 404 que busco la
    # solicitud y no la encontro; 503 que llego al almacen y el almacen no
    # esta (en este ambiente no hay MongoDB, y eso esta declarado como
    # limitacion). Los dos ultimos sirven: en ambos el cuerpo XML se leyo.
    assert codigo != 400, cuerpo
    assert codigo in (404, 503), cuerpo
    if codigo == 503:
        assert json.loads(cuerpo)["error"]["codigo"] == "ALMACEN_NO_DISPONIBLE", (
            "Una caida del almacen debe decirse con su propio codigo y 503, "
            f"no como error interno. Respuesta: {cuerpo}")


def test_el_estado_vacio_en_xml_si_se_rechaza(proceso_node, token_especialista):
    """El contraste de la prueba anterior: sin <estado>, el servicio lo nota.

    Sin esta, la afirmacion "no respondio ESTADO_INVALIDO" no probaria nada:
    habria que creer que ese codigo aparece cuando falta el estado. Aqui se
    comprueba que aparece.
    """
    cambio = ENVOLTURA.format(raiz="CambioEstadoSolicitud",
                              cuerpo="<nota>Sin estado a proposito</nota>")
    codigo, _, cuerpo = http("PATCH", proceso_node,
                             "/api/v1/solicitudes-apoyo/no-existe-este-id/estado",
                             token_especialista, cuerpo_xml=cambio)
    assert codigo == 400, cuerpo
    assert json.loads(cuerpo)["error"]["codigo"] == "ESTADO_INVALIDO"


def test_las_dos_bibliotecas_leen_el_mismo_xml_igual(catalogo_node):
    """El mismo cuerpo XML tiene que significar lo mismo en Python y en Node.

    No se compara contra una constante escrita a mano: se corre el lector de
    Node y el de Python sobre el MISMO texto y se comparan los resultados. Si
    alguien cambia una regla en un lenguaje y no en el otro, esta prueba lo
    dice.
    """
    import subprocess
    import sys
    from comun.xmlizar import de_xml

    texto = ENVOLTURA.format(raiz="Caso", cuerpo=(
        "<cadena>texto</cadena>"
        "<ceros>007</ceros>"
        "<decimal>1.0</decimal>"
        "<nulo xsi:nil=\"true\"/>"
        "<vacio></vacio>"
        "<anidado><a>1</a><b>2</b></anidado>"
        "<etiquetas><etiqueta>uno</etiqueta><etiqueta>dos</etiqueta></etiquetas>"))

    guion = ("import('/home/claude/repo/apps/microservicios/comun-node/src/"
             "cuerpoXml.js').then(m=>{"
             "let t='';process.stdin.on('data',d=>t+=d);"
             "process.stdin.on('end',()=>"
             "console.log(JSON.stringify(m.deXml(t))));});")
    guion = guion.replace("/home/claude/repo", os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    try:
        salida = subprocess.run(["node", "--input-type=module", "-e", guion],
                                input=texto, capture_output=True, text=True,
                                timeout=30)
    except FileNotFoundError:
        pytest.skip("Node no esta disponible")
    assert salida.returncode == 0, salida.stderr
    assert json.loads(salida.stdout) == de_xml(texto), (
        "El lector de Node y el de Python no interpretan igual el mismo XML.\n"
        f"Node:   {salida.stdout.strip()}\n"
        f"Python: {json.dumps(de_xml(texto))}")
    assert sys.version_info >= (3, 8)
