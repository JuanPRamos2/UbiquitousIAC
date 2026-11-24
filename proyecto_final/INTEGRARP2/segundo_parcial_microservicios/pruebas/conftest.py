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
                       "notif_sin_leer:*"):
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


def cab(token, xml=False):
    h = {"Authorization": f"Bearer {token}"}
    if xml:
        h["Accept"] = "application/xml"
    return h
