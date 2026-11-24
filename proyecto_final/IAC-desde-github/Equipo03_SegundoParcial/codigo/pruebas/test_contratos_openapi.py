"""
Validación de los contratos OpenAPI de los cuatro microservicios.

Un Swagger que no se comprueba contra el servicio real describe lo que
alguien quiso hacer, no lo que el servicio hace. Estas pruebas verifican
que cada ruta documentada exista de verdad y que cada ruta real esté
documentada.
"""
import pytest

SERVICIOS = ["auth", "users", "documentos", "notificaciones"]


@pytest.fixture
def clientes(auth, users, documentos, notificaciones):
    return {"auth": auth, "users": users,
            "documentos": documentos, "notificaciones": notificaciones}


def test_cada_servicio_publica_su_contrato(clientes):
    for nombre, c in clientes.items():
        r = c.get("/openapi.json")
        assert r.status_code == 200, nombre
        d = r.get_json()
        assert d["openapi"].startswith("3.0"), nombre
        assert d["info"]["title"], nombre
        assert d["paths"], nombre


def test_cada_servicio_sirve_swagger_ui(clientes):
    for nombre, c in clientes.items():
        r = c.get("/docs")
        assert r.status_code == 200, nombre
        html = r.get_data(as_text=True)
        assert "SwaggerUIBundle" in html
        # Swagger UI se sirve desde el propio servicio: si la red de la
        # demostracion bloquea un CDN, la documentacion igual abre.
        assert "cdn" not in html.lower()
        assert "/estaticos/swagger/swagger-ui-bundle.js" in html


def test_swagger_ui_esta_empaquetado(clientes):
    for nombre, c in clientes.items():
        for recurso in ("swagger-ui-bundle.js", "swagger-ui.css"):
            r = c.get(f"/estaticos/swagger/{recurso}")
            assert r.status_code == 200, f"{nombre}/{recurso}"


def test_todas_las_rutas_documentadas_existen(clientes):
    """Si el contrato describe una ruta que no existe, el cliente la llamara."""
    import re
    for nombre, c in clientes.items():
        contrato = c.get("/openapi.json").get_json()
        reales = {str(r.rule) for r in c.application.url_map.iter_rules()}
        # Se normaliza {param} de OpenAPI a <param> de Flask.
        for ruta in contrato["paths"]:
            flask_rule = re.sub(r"\{(\w+)\}", r"<\1>", ruta)
            candidatos = {flask_rule,
                          re.sub(r"<(\w+)>", r"<int:\1>", flask_rule)}
            assert candidatos & reales, f"{nombre}: {ruta} documentada pero no existe"


def test_todas_las_rutas_reales_estan_documentadas(clientes):
    """Lo contrario también: una ruta sin documentar es una sorpresa."""
    import re
    exentas = re.compile(r"^/(health|docs|openapi\.json|estaticos)")
    for nombre, c in clientes.items():
        contrato = c.get("/openapi.json").get_json()
        documentadas = {re.sub(r"\{(\w+)\}", r"<\1>", r) for r in contrato["paths"]}
        for regla in c.application.url_map.iter_rules():
            ruta = str(regla.rule)
            if exentas.match(ruta) or ruta == "/static/<path:filename>":
                continue
            normalizada = re.sub(r"<int:(\w+)>", r"<\1>", ruta)
            assert normalizada in documentadas, \
                f"{nombre}: {ruta} existe pero no esta en el contrato"


def test_el_contrato_declara_seguridad_jwt(clientes):
    for nombre, c in clientes.items():
        d = c.get("/openapi.json").get_json()
        esquema = d["components"]["securitySchemes"]["bearerAuth"]
        assert esquema["scheme"] == "bearer"
        assert esquema["bearerFormat"] == "JWT"
        assert d["security"] == [{"bearerAuth": []}]


def test_el_contrato_documenta_los_codigos_http_de_error(clientes):
    """La rubrica pide respuestas exitosas y de error documentadas."""
    esperados = {"400", "401", "403", "404", "422", "429", "500"}
    for nombre, c in clientes.items():
        d = c.get("/openapi.json").get_json()
        for ruta, metodos in d["paths"].items():
            for metodo, op in metodos.items():
                codigos = set(op["responses"])
                assert codigos & {"200", "201"}, f"{nombre} {metodo} {ruta}: sin exito"
                faltan = esperados - codigos
                assert not faltan, f"{nombre} {metodo} {ruta}: faltan {sorted(faltan)}"


def test_los_errores_traen_ejemplo_json_y_xml(clientes):
    """La rubrica pide ejemplo JSON y ejemplo XML en Swagger."""
    for nombre, c in clientes.items():
        d = c.get("/openapi.json").get_json()
        for clave, resp in d["components"]["responses"].items():
            tipos = set(resp["content"])
            assert tipos == {"application/json", "application/xml"}, \
                f"{nombre}/{clave}: {tipos}"
            assert resp["content"]["application/xml"]["example"].startswith("<?xml")


def test_login_y_renovar_no_exigen_token(clientes):
    """Pedir token para iniciar sesion seria un circulo imposible de cerrar."""
    d = clientes["auth"].get("/openapi.json").get_json()
    assert d["paths"]["/api/v1/auth/login"]["post"]["security"] == []
    assert d["paths"]["/api/v1/auth/renovar"]["post"]["security"] == []
    # Las demas si lo exigen (heredan la seguridad global).
    assert "security" not in d["paths"]["/api/v1/auth/logout"]["post"]
