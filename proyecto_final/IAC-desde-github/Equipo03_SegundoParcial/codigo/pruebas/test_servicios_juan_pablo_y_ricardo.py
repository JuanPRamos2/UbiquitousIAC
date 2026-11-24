"""
Los ocho servicios de Juan Pablo y Ricardo abren, documentan y exigen token.

No necesitan PostgreSQL ni Redis: /health/live y /docs no tocan la base,
y una ruta protegida sin Authorization responde 401 antes de consultar
Redis. Eso es lo que se puede comprobar en cualquier máquina.
"""
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "apps", "microservicios", "comun"))

SERVICIOS = [
    ("consent-service", 8110, "/api/v1/consentimiento/aviso"),
    ("privacy-service", 8111, "/api/v1/privacidad/umbral"),
    ("audit-service", 8118, "/api/v1/auditoria"),
    ("data-governance-service", 8119, "/api/v1/gobernanza/minimizacion"),
]


def _cargar(nombre):
    import importlib.util
    carpeta = os.path.join(RAIZ, "apps", "microservicios", nombre)
    sys.path.insert(0, carpeta)
    try:
        spec = importlib.util.spec_from_file_location(f"svc_{nombre}", 
                                                       os.path.join(carpeta, "app.py"))
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = modulo
        spec.loader.exec_module(modulo)
    finally:
        sys.path.remove(carpeta)
        sys.modules.pop("contrato", None)
    return modulo


@pytest.mark.parametrize("nombre,puerto,ruta", SERVICIOS)
def test_el_servicio_vive_documenta_y_exige_token(nombre, puerto, ruta):
    modulo = _cargar(nombre)
    cliente = modulo.app.test_client()

    vivo = cliente.get("/health/live")
    assert vivo.status_code == 200, vivo.get_data(as_text=True)
    assert vivo.get_json()["servicio"] == nombre

    salud = cliente.get("/health")
    assert salud.status_code == 200
    assert salud.get_json()["version"] == "v1"

    docs = cliente.get("/docs")
    assert docs.status_code == 200
    assert b"swagger" in docs.data.lower()

    contrato = cliente.get("/openapi.json")
    assert contrato.status_code == 200
    cuerpo = contrato.get_json()
    assert cuerpo["openapi"] == "3.0.3"
    assert any(str(puerto) in s["url"] for s in cuerpo["servers"])
    ruta_doc = ruta.replace("<", "{").replace(">", "}")
    assert ruta_doc in cuerpo["paths"], ruta_doc
    assert "bearerAuth" in cuerpo["components"]["securitySchemes"]

    sin_token = cliente.get(ruta)
    assert sin_token.status_code == 401, sin_token.get_data(as_text=True)
    assert sin_token.get_json()["error"]["codigo"] == "TOKEN_AUSENTE"


def test_la_politica_de_privacidad_no_calcula_laplace_en_el_servicio():
    """Si el ruido estuviera en este archivo, nadie podría señalar dónde está."""
    ruta = os.path.join(RAIZ, "apps", "microservicios", "privacy-service", "app.py")
    fuente = open(ruta, encoding="utf-8").read()
    assert "fn_ruido_laplace" in fuente
    assert "def " not in fuente.split("fn_ruido_laplace", 1)[0][-40:]
    # El servicio nombra la función. No la reimplementa.
    assert "random" not in fuente
    assert "exp(" not in fuente


def test_la_baja_de_datos_declara_que_no_borra():
    ruta = os.path.join(RAIZ, "apps", "microservicios",
                        "data-governance-service", "app.py")
    fuente = open(ruta, encoding="utf-8").read()
    assert "DELETE FROM" not in fuente.upper()
    assert "borrado" in fuente


def test_los_servicios_de_ricardo_estan_en_node():
    """Sus seis servicios los subió él en Node. No deben volver a ser Flask."""
    raiz = os.path.join(RAIZ, "apps", "microservicios")
    for nombre in ("catalog-service", "main-process-service", "survey-service",
                   "indicators-service", "support-service", "organizational-service"):
        carpeta = os.path.join(raiz, nombre)
        assert os.path.isfile(os.path.join(carpeta, "package.json")), nombre
        assert not os.path.isfile(os.path.join(carpeta, "app.py")), nombre
