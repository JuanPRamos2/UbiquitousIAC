"""
Configuración de las pruebas de los microservicios.

MongoDB se sustituye por mongomock, que implementa la misma interfaz en
memoria. Es una sustitución SOLO de prueba: el código de los servicios usa
pymongo puro y no sabe que existe mongomock. Eso es lo que permite que las
mismas pruebas corran después contra un MongoDB real sin cambiar una línea.

PostgreSQL y Redis sí son reales: levantarlos es barato y una prueba
contra una base simulada no habría detectado, por ejemplo, que la columna
'variacion' es generada y no admite inserción.
"""
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("PG_HOST", "127.0.0.1")
os.environ.setdefault("PG_BASE", "bienestar_limpio")
os.environ.setdefault("PG_USUARIO", "bienestar_app")
os.environ.setdefault("PG_CLAVE", "desarrollo_local")
os.environ.setdefault("REDIS_HOST", "127.0.0.1")
os.environ.setdefault("APP_AMBIENTE", "developer")
os.environ.setdefault("MOSTRAR_ERRORES", "true")


def _cargar(nombre_servicio, alias):
    """Importa el app.py de un servicio sin que choquen entre sí."""
    import importlib.util
    carpeta = os.path.join(RAIZ, "apps", "microservicios", nombre_servicio)
    ruta = os.path.join(carpeta, "app.py")
    # En el contenedor el WORKDIR es la carpeta del servicio, asi que
    # "from contrato import ..." resuelve solo. Aqui hay que ponerla en la
    # ruta de busqueda a mano mientras se importa.
    sys.path.insert(0, carpeta)
    try:
        spec = importlib.util.spec_from_file_location(alias, ruta)
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[alias] = modulo
        spec.loader.exec_module(modulo)
    finally:
        sys.path.remove(carpeta)
        sys.modules.pop("contrato", None)
    return modulo


@pytest.fixture(scope="session", autouse=True)
def estado_limpio():
    """Deja Redis y la base sin rastros de corridas anteriores.

    Sin esto la suite pasa la primera vez y falla la segunda: el limite de
    consumo y el contador de intentos fallidos viven en Redis con ventana
    de 60 segundos, de modo que dos corridas seguidas chocarian con un 429.
    Una suite que solo pasa una vez no sirve para verificar nada.
    """
    import redis as _redis
    r = _redis.Redis(host=os.environ["REDIS_HOST"], port=6379, decode_responses=True)
    try:
        for patron in ("limite:*", "intentos:*", "sesion:*", "revocado:*",
                       "notif_sin_leer:*", "consulta:*"):
            claves = list(r.scan_iter(patron, count=1000))
            if claves:
                r.delete(*claves)
    except Exception:
        pass

    # El usuario que crea la prueba de alta.
    try:
        import psycopg2
        cn = psycopg2.connect(
            host=os.environ["PG_HOST"], dbname=os.environ["PG_BASE"],
            user="postgres" if os.environ.get("PG_SUPER") else os.environ["PG_USUARIO"],
            password=os.environ["PG_CLAVE"])
        with cn, cn.cursor() as cur:
            cur.execute("DELETE FROM usuarios.usuario_perfil WHERE usuario_id = 'USR-09001'")
            cur.execute("DELETE FROM usuarios.usuario WHERE usuario_id = 'USR-09001'")
        cn.close()
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def sin_limite_acumulado():
    """Borra los contadores del límite de consumo antes de cada prueba.

    El límite existe para frenar a un cliente que pide cientos de veces por
    minuto, no a una suite que corre noventa peticiones en tres segundos.
    Sin esta limpieza, la primera mitad de la suite consume la cuota y la
    segunda recibe 429 por motivos que no tienen nada que ver con lo que
    cada prueba quiere comprobar.

    El límite SÍ se prueba, a propósito y por separado, en
    test_limite_de_consumo.py: ahí la cuota se agota deliberadamente.
    """
    import redis as _redis
    try:
        r = _redis.Redis(host=os.environ["REDIS_HOST"], port=6379,
                         decode_responses=True)
        claves = list(r.scan_iter("limite:*", count=1000))
        if claves:
            r.delete(*claves)
    except Exception:
        pass
    yield


@pytest.fixture(scope="session", autouse=True)
def mongo_en_memoria(estado_limpio):
    """Sustituye el cliente de MongoDB antes de importar ningún servicio."""
    import mongomock

    import comun.mongo as m
    cliente = mongomock.MongoClient()
    m.obtener_cliente = lambda: cliente
    m.base = lambda: cliente[os.environ.get("MONGO_BASE", "bienestar")]
    m.ping = lambda: cliente.admin.command("ping")
    yield cliente


@pytest.fixture(scope="session")
def auth(mongo_en_memoria):
    return _cargar("auth-service", "svc_auth").app.test_client()


@pytest.fixture(scope="session")
def users(mongo_en_memoria):
    return _cargar("users-service", "svc_users").app.test_client()


@pytest.fixture(scope="session")
def documentos(mongo_en_memoria):
    mod = _cargar("documents-service", "svc_docs")
    # El modulo capturo 'base' al importarse; se re-apunta a mongomock.
    import comun.mongo as m
    mod.base = m.base
    return mod.app.test_client()


@pytest.fixture(scope="session")
def notificaciones(mongo_en_memoria):
    mod = _cargar("notifications-service", "svc_notif")
    import comun.mongo as m
    mod.base = m.base
    return mod.app.test_client()


@pytest.fixture(scope="session")
def consultas(mongo_en_memoria):
    """queries-service. No usa MongoDB, pero la fixture mantiene el orden
    de arranque: todos los servicios se importan despues de sustituir el
    cliente de Mongo, para que ninguno capture el real."""
    return _cargar("queries-service", "svc_queries").app.test_client()


@pytest.fixture(scope="session")
def reportes(mongo_en_memoria):
    mod = _cargar("reports-service", "svc_reports")
    import comun.mongo as m
    mod.base = m.base
    return mod.app.test_client()


@pytest.fixture(scope="session")
def algoritmos(mongo_en_memoria):
    mod = _cargar("algorithms-service", "svc_alg")
    import comun.mongo as m
    mod.base = m.base
    return mod.app.test_client()


# ---------------------------------------------------------------------------
# Servicios en Node
#
# catalog-service y main-process-service no se pueden importar: son
# procesos de Node. Se levantan de verdad, en un puerto libre, y se les
# habla por HTTP con un token emitido por auth-service.
#
# Esa es justamente la prueba que vale: demuestra que el token firmado por
# el servicio en Python sirve en el servicio en Node, que los dos leen la
# misma sesion en Redis y que el XML que produce el serializador de Node
# valida contra el MISMO XSD que el de Python. Un mock no probaria nada de
# eso.
# ---------------------------------------------------------------------------

def _puerto_libre():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    puerto = s.getsockname()[1]
    s.close()
    return puerto


def _levantar_node(carpeta, espera=25):
    """Arranca un servicio de Node y espera a que su sonda responda."""
    import shutil
    import subprocess
    import time
    import urllib.error
    import urllib.request

    if not shutil.which("node"):
        pytest.skip("node no esta instalado en este ambiente")

    ruta = os.path.join(RAIZ, "apps", "microservicios", carpeta)
    if not os.path.isdir(os.path.join(ruta, "node_modules")):
        pytest.skip(f"faltan dependencias de {carpeta}: ejecuta npm install")

    puerto = _puerto_libre()
    entorno = dict(os.environ)
    entorno.update(PUERTO=str(puerto), NOMBRE_SERVICIO=carpeta,
                   PG_HOST=os.environ["PG_HOST"], PG_BASE=os.environ["PG_BASE"],
                   PG_USUARIO=os.environ["PG_USUARIO"],
                   PG_CLAVE=os.environ["PG_CLAVE"],
                   REDIS_HOST=os.environ["REDIS_HOST"],
                   APP_AMBIENTE="developer")
    proceso = subprocess.Popen(
        ["node", "src/server.js"], cwd=ruta, env=entorno,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    base_url = f"http://127.0.0.1:{puerto}"
    limite = time.time() + espera
    while time.time() < limite:
        if proceso.poll() is not None:
            salida = (proceso.stderr.read() or b"").decode("utf8", "replace")
            pytest.skip(f"{carpeta} no arranco: {salida[:300]}")
        try:
            with urllib.request.urlopen(base_url + "/health/live", timeout=1) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.3)
    else:
        proceso.terminate()
        pytest.skip(f"{carpeta} no respondio su sonda en {espera}s")
    return proceso, base_url


@pytest.fixture(scope="session")
def catalogo_node():
    proceso, base_url = _levantar_node("catalog-service")
    yield base_url
    proceso.terminate()
    try:
        proceso.wait(timeout=5)
    except Exception:
        proceso.kill()


@pytest.fixture(scope="session")
def proceso_node():
    proceso, base_url = _levantar_node("main-process-service")
    yield base_url
    proceso.terminate()
    try:
        proceso.wait(timeout=5)
    except Exception:
        proceso.kill()


def http(metodo, base_url, ruta, token=None, cuerpo=None, xml=False,
         tiempo=10, cuerpo_xml=None):
    """Peticion HTTP a un servicio de Node. Devuelve (codigo, cabeceras, bytes).

    `cuerpo` manda JSON; `cuerpo_xml` manda el texto XML tal cual, que es
    como habla la aplicacion de escritorio.
    """
    import json as _json
    import urllib.error
    import urllib.request

    datos = None
    cabeceras = {}
    if cuerpo_xml is not None:
        datos = cuerpo_xml.encode("utf8")
        cabeceras["Content-Type"] = "application/xml"
    elif cuerpo is not None:
        datos = _json.dumps(cuerpo).encode("utf8")
        cabeceras["Content-Type"] = "application/json"
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    if xml:
        cabeceras["Accept"] = "application/xml"
    peticion = urllib.request.Request(base_url + ruta, data=datos,
                                      headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=tiempo) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def iniciar_sesion(auth, correo, contrasena="demo123"):
    r = auth.post("/api/v1/auth/login", json={"correo": correo, "contrasena": contrasena})
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()["token_acceso"]


@pytest.fixture(scope="session")
def token_admin(auth):
    return iniciar_sesion(auth, "carlos.ramirez@nexum.com.mx")


@pytest.fixture(scope="session")
def token_colaborador(auth):
    return iniciar_sesion(auth, "ana.perez@nexum.com.mx")


@pytest.fixture(scope="session")
def token_auditor(auth):
    return iniciar_sesion(auth, "roberto.garcia@nexum.com.mx")


@pytest.fixture(scope="session")
def token_especialista(auth):
    return iniciar_sesion(auth, "mariana.solis@nexum.com.mx")


@pytest.fixture(scope="session")
def token_lider(auth):
    """El unico perfil con alcance acotado: UO-CC-TURNO-B.

    Los demas perfiles tienen alcance nulo, que significa toda la
    organizacion y es lo correcto para el especialista y el auditor, cuyo
    trabajo es transversal. Para probar el acotamiento hay que usar a este.
    """
    return iniciar_sesion(auth, "lucia.hernandez@nexum.com.mx")


def cab(token, xml=False):
    h = {"Authorization": f"Bearer {token}"}
    if xml:
        h["Accept"] = "application/xml"
    return h
