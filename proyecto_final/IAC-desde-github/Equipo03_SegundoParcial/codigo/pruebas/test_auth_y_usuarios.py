"""
Pruebas de auth-service y users-service (Integrante 1).

Cubren las cuatro evidencias que pide el reparto de trabajo: usuario
autorizado, usuario sin permisos, token inválido y sesión revocada.
"""
from conftest import cab, iniciar_sesion


# --------------------------------------------------------------- salud
def test_endpoints_de_salud(auth, users):
    for cliente in (auth, users):
        assert cliente.get("/health/live").status_code == 200
        assert cliente.get("/health").status_code == 200
        r = cliente.get("/health/ready")
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json()["estado"] == "listo"


# ------------------------------------------------------------- login
def test_login_correcto_devuelve_los_dos_tokens(auth):
    r = auth.post("/api/v1/auth/login",
                  json={"correo": "carlos.ramirez@nexum.com.mx", "contrasena": "demo123"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["token_acceso"] and d["token_renovacion"]
    assert d["tipo_token"] == "Bearer"
    assert d["usuario"]["perfil"] == "Administrador del sistema"


def test_login_no_distingue_correo_de_contrasena(auth):
    """Decir cuál de los dos falló permitiría averiguar qué correos existen."""
    a = auth.post("/api/v1/auth/login",
                  json={"correo": "noexiste@nexum.com.mx", "contrasena": "x"})
    b = auth.post("/api/v1/auth/login",
                  json={"correo": "carlos.ramirez@nexum.com.mx", "contrasena": "malisima"})
    assert a.status_code == b.status_code == 401
    assert a.get_json()["error"]["codigo"] == b.get_json()["error"]["codigo"]
    assert a.get_json()["error"]["mensaje"] == b.get_json()["error"]["mensaje"]


def test_login_sin_campos_devuelve_todos_los_problemas(auth):
    r = auth.post("/api/v1/auth/login", json={})
    assert r.status_code == 400
    campos = {d["campo"] for d in r.get_json()["error"]["detalles"]}
    assert campos == {"correo", "contrasena"}


# ------------------------------------------------- las cuatro evidencias
def test_evidencia_usuario_autorizado(users, token_admin):
    r = users.get("/api/v1/usuarios?tamano=5", headers=cab(token_admin))
    assert r.status_code == 200
    d = r.get_json()
    assert d["paginacion"]["total"] >= 1
    assert len(d["usuarios"]) <= 5


def test_evidencia_usuario_sin_permisos(users, token_colaborador):
    r = users.get("/api/v1/usuarios", headers=cab(token_colaborador))
    assert r.status_code == 403
    assert r.get_json()["error"]["codigo"] == "SIN_PERMISO"


def test_evidencia_token_invalido(users):
    r = users.get("/api/v1/usuarios", headers=cab("no.es.un.token"))
    assert r.status_code == 401
    assert r.get_json()["error"]["codigo"] == "TOKEN_INVALIDO"


def test_evidencia_token_ausente(users):
    r = users.get("/api/v1/usuarios")
    assert r.status_code == 401
    assert r.get_json()["error"]["codigo"] == "TOKEN_AUSENTE"


def test_evidencia_sesion_revocada(auth, users):
    token = iniciar_sesion(auth, "carlos.ramirez@nexum.com.mx")
    assert users.get("/api/v1/usuarios", headers=cab(token)).status_code == 200

    assert auth.post("/api/v1/auth/logout", headers=cab(token)).status_code == 200

    r = users.get("/api/v1/usuarios", headers=cab(token))
    assert r.status_code == 401
    assert r.get_json()["error"]["codigo"] == "SESION_REVOCADA"


# ------------------------------------------------------------ renovación
def test_renovacion_rota_la_sesion_anterior(auth):
    r = auth.post("/api/v1/auth/login",
                  json={"correo": "mariana.solis@nexum.com.mx", "contrasena": "demo123"})
    viejo_acceso = r.get_json()["token_acceso"]
    renovacion = r.get_json()["token_renovacion"]

    nuevo = auth.post("/api/v1/auth/renovar", json={"token_renovacion": renovacion})
    assert nuevo.status_code == 200
    assert nuevo.get_json()["token_acceso"] != viejo_acceso

    # El token anterior deja de servir: si siguiera sirviendo, robarlo
    # daria acceso indefinido pese a la renovacion.
    assert auth.get("/api/v1/auth/validar",
                    headers=cab(viejo_acceso)).status_code == 401


def test_un_token_de_acceso_no_sirve_para_renovar(auth, token_auditor):
    r = auth.post("/api/v1/auth/renovar", json={"token_renovacion": token_auditor})
    assert r.status_code == 401
    assert r.get_json()["error"]["codigo"] == "TIPO_DE_TOKEN_INCORRECTO"


# ------------------------------------------------- permisos y validación
def test_los_permisos_no_viajan_en_el_token(auth, token_auditor):
    """Se consultan en cada peticion, para que revocarlos surta efecto ya."""
    import jwt
    carga = jwt.decode(token_auditor, options={"verify_signature": False})
    assert "permisos" not in carga

    r = auth.get("/api/v1/auth/permisos", headers=cab(token_auditor))
    assert r.status_code == 200
    assert "BITACORA_CONSULTAR" in r.get_json()["permisos"]


def test_alta_de_usuario_valida_todo_de_una_vez(users, token_admin):
    r = users.post("/api/v1/usuarios", headers=cab(token_admin),
                   json={"usuario_id": "malo", "correo": "no-es-correo",
                         "nombre": "A", "apellido_paterno": "B",
                         "contrasena": "corta", "perfil_id": "uno"})
    assert r.status_code == 422
    campos = {d["campo"] for d in r.get_json()["error"]["detalles"]}
    assert campos == {"usuario_id", "correo", "nombre", "apellido_paterno",
                      "contrasena", "perfil_id"}


def test_alta_y_cambio_de_perfil(users, token_admin):
    nuevo = {"usuario_id": "USR-09001", "correo": "prueba.alta@nexum.com.mx",
             "nombre": "Prueba", "apellido_paterno": "Alta",
             "contrasena": "contrasena-larga", "perfil_id": 1}
    users.delete  # no existe borrado: los usuarios se inactivan
    r = users.post("/api/v1/usuarios", headers=cab(token_admin), json=nuevo)
    assert r.status_code in (201, 409), r.get_data(as_text=True)

    # Duplicado: la segunda alta debe ser rechazada con 409.
    r2 = users.post("/api/v1/usuarios", headers=cab(token_admin), json=nuevo)
    assert r2.status_code == 409
    assert r2.get_json()["error"]["codigo"] in ("USUARIO_DUPLICADO", "CORREO_DUPLICADO")

    r3 = users.put("/api/v1/usuarios/USR-09001/perfil",
                   headers=cab(token_admin), json={"perfil_id": 4})
    assert r3.status_code == 200
    assert r3.get_json()["perfil_id"] == 4


def test_un_admin_no_puede_desactivarse_a_si_mismo(users, token_admin):
    r = users.put("/api/v1/usuarios/USR-00002/estado",
                  headers=cab(token_admin), json={"activo": False})
    assert r.status_code == 409
    assert r.get_json()["error"]["codigo"] == "OPERACION_NO_PERMITIDA"


def test_paginacion_rechaza_tamanos_abusivos(users, token_admin):
    r = users.get("/api/v1/usuarios?tamano=5000", headers=cab(token_admin))
    assert r.status_code == 400
    assert r.get_json()["error"]["codigo"] == "PARAMETRO_INVALIDO"


# ------------------------------------------------------------------ XML
def test_la_misma_respuesta_en_xml(users, token_admin):
    from lxml import etree
    r = users.get("/api/v1/usuarios?tamano=2", headers=cab(token_admin, xml=True))
    assert r.status_code == 200
    assert r.mimetype == "application/xml"
    raiz = etree.fromstring(r.get_data())
    ns = {"b": "http://nexum.com.mx/bienestar/v1"}
    assert raiz.tag.endswith("usuarios_respuesta")
    assert len(raiz.findall(".//b:usuarios/b:usuario", ns)) <= 2
    assert raiz.find(".//b:paginacion/b:pagina", ns).text == "1"


def test_los_errores_tambien_se_entregan_en_xml(users, token_colaborador):
    from lxml import etree
    r = users.get("/api/v1/usuarios", headers=cab(token_colaborador, xml=True))
    assert r.status_code == 403
    raiz = etree.fromstring(r.get_data())
    ns = {"b": "http://nexum.com.mx/bienestar/v1"}
    assert raiz.find(".//b:error/b:codigo", ns).text == "SIN_PERMISO"
