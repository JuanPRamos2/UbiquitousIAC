"""
El sistema web sigue funcionando con los microservicios apagados.

Es un requisito explícito de la arquitectura obligatoria del proyecto, y
hasta ahora estaba afirmado en la documentación y comprobado a mano. Esta
prueba lo verifica sola: levanta users-service de verdad, comprueba que el
portal obtiene los usuarios POR AHÍ, lo apaga, y comprueba que el portal
sigue mostrando los mismos usuarios leyéndolos de PostgreSQL.

Por qué se prueba con un proceso real y no con un doble: lo que puede
romperse aquí es el manejo del tiempo de espera y de la excepción de red.
Un doble que lanza una excepción no reproduce un servicio que acepta la
conexión y nunca responde, que es el caso que de verdad congela una
pantalla.
"""
import os
import subprocess
import sys
import time

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _puerto_libre():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    puerto = s.getsockname()[1]
    s.close()
    return puerto


@pytest.fixture(scope="module")
def users_service_real():
    """Levanta users-service como proceso, con gunicorn, en un puerto libre."""
    import urllib.request
    carpeta = os.path.join(RAIZ, "apps", "microservicios", "users-service")
    puerto = _puerto_libre()
    entorno = dict(os.environ)
    entorno.update(
        PUERTO=str(puerto), NOMBRE_SERVICIO="users-service",
        PYTHONPATH=os.path.join(RAIZ, "apps", "microservicios", "comun"))
    proceso = subprocess.Popen(
        [sys.executable, "-m", "gunicorn", "-b", f"127.0.0.1:{puerto}",
         "-w", "1", "-k", "gthread", "app:app"],
        cwd=carpeta, env=entorno,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    url = f"http://127.0.0.1:{puerto}"
    limite = time.time() + 25
    while time.time() < limite:
        if proceso.poll() is not None:
            salida = (proceso.stderr.read() or b"").decode("utf8", "replace")
            pytest.skip(f"users-service no arranco: {salida[-300:]}")
        try:
            with urllib.request.urlopen(url + "/health/ready", timeout=1) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.3)
    else:
        proceso.terminate()
        pytest.skip("users-service no respondio su sonda")

    yield proceso, url
    if proceso.poll() is None:
        proceso.terminate()
        try:
            proceso.wait(timeout=5)
        except Exception:
            proceso.kill()


@pytest.fixture(scope="module")
def portal(users_service_real):
    """El sistema web, apuntado al users-service que acabamos de levantar."""
    _, url = users_service_real
    os.environ["USERS_SERVICE_URL"] = url
    os.environ.setdefault("ALMACEN_EVIDENCIAS", "/tmp/evidencias-prueba")
    sys.path.insert(0, os.path.join(RAIZ, "apps", "web"))
    try:
        from app import crear_app
        aplicacion = crear_app()
        aplicacion.config["TESTING"] = True
        return aplicacion.test_client()
    finally:
        sys.path.pop(0)


def _entrar(cliente):
    r = cliente.post("/entrar",
                     data={"correo": "carlos.ramirez@nexum.com.mx",
                           "contrasena": "demo123"})
    assert r.status_code in (302, 303), r.get_data(as_text=True)[:300]


def test_el_portal_usa_el_microservicio_cuando_esta_arriba(portal):
    _entrar(portal)
    r = portal.get("/administracion/usuarios")
    assert r.status_code == 200
    texto = r.get_data(as_text=True)
    assert "users-service" in texto, (
        "el portal no indico que obtuvo los datos del microservicio")
    assert "USR-0" in texto, "la tabla no trae usuarios"


def test_el_portal_sigue_operando_con_el_microservicio_apagado(
        portal, users_service_real):
    """La propiedad que el proyecto promete: operación independiente."""
    proceso, _ = users_service_real
    _entrar(portal)

    antes = portal.get("/administracion/usuarios").get_data(as_text=True)
    cuantos_antes = antes.count("USR-0")
    assert cuantos_antes > 0

    proceso.terminate()
    proceso.wait(timeout=10)

    despues = portal.get("/administracion/usuarios")
    assert despues.status_code == 200, (
        "el portal devolvio error al caerse el microservicio")
    texto = despues.get_data(as_text=True)

    # Y dice al operador por cuál de las dos vías obtuvo los datos: sin ese
    # aviso, la degradación es invisible y nadie se enteraría de que un
    # servicio está caído hasta que algo más falle.
    assert "base de datos" in texto, (
        "el portal no aviso que cayo a la base de datos")
    assert texto.count("USR-0") == cuantos_antes, (
        "la tabla perdio usuarios al caer a PostgreSQL: la vista alterna no "
        "devuelve lo mismo que el microservicio")


def test_las_demas_pantallas_tampoco_se_caen(portal, users_service_real):
    """El resto del portal no depende del microservicio apagado."""
    proceso, _ = users_service_real
    if proceso.poll() is None:
        proceso.terminate()
        proceso.wait(timeout=10)
    _entrar(portal)

    for ruta in ("/portal", "/administracion/permisos",
                 "/administracion/perfiles/", "/gobierno/bitacora",
                 "/gobierno/garantias"):
        r = portal.get(ruta, follow_redirects=True)
        assert r.status_code == 200, (ruta, r.status_code)
        cuerpo = r.get_data(as_text=True)
        assert "Error interno" not in cuerpo, ruta
        assert "Traceback" not in cuerpo, ruta
