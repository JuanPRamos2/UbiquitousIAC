"""
Validación de las respuestas JSON contra los esquemas generados.

Mismo criterio que con los XSD: un esquema que nadie comprueba contra
respuestas reales describe lo que alguien quiso hacer, no lo que el
servicio hace.
"""
import json
import os

import pytest
from conftest import cab
from jsonschema import Draft202012Validator

JSON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "contratos", "json")


def esquema(nombre):
    with open(os.path.join(JSON_DIR, f"{nombre}.schema.json"), encoding="utf8") as f:
        return json.load(f)


def validar(datos, nombre):
    v = Draft202012Validator(esquema(nombre))
    errores = sorted(v.iter_errors(datos), key=lambda e: list(e.path))
    if errores:
        pytest.fail(f"La respuesta no cumple {nombre}.schema.json:\n" +
                    "\n".join(f"  {list(e.path)}: {e.message}" for e in errores[:6]))


def test_todos_los_esquemas_son_validos():
    import glob
    archivos = glob.glob(os.path.join(JSON_DIR, "*.schema.json"))
    assert len(archivos) >= 10
    for a in archivos:
        with open(a, encoding="utf8") as f:
            Draft202012Validator.check_schema(json.load(f))


def test_sesion_cumple_su_esquema(auth):
    r = auth.post("/api/v1/auth/login",
                  json={"correo": "lucia.hernandez@nexum.com.mx",
                        "contrasena": "demo123"})
    assert r.status_code == 200
    validar(r.get_json(), "Sesion")


def test_validacion_cumple_su_esquema(auth, token_admin):
    r = auth.get("/api/v1/auth/validar", headers=cab(token_admin))
    validar(r.get_json(), "Validacion")


def test_lista_de_usuarios_cumple_su_esquema(users, token_admin):
    r = users.get("/api/v1/usuarios?tamano=5", headers=cab(token_admin))
    validar(r.get_json(), "ListaUsuarios")


def test_cada_usuario_cumple_su_esquema(users, token_admin):
    r = users.get("/api/v1/usuarios?tamano=10", headers=cab(token_admin))
    for u in r.get_json()["usuarios"]:
        validar(u, "Usuario")


def test_el_error_cumple_su_esquema(users, token_colaborador):
    r = users.get("/api/v1/usuarios", headers=cab(token_colaborador))
    assert r.status_code == 403
    validar(r.get_json(), "Error")


def test_el_error_de_validacion_cumple_su_esquema(users, token_admin):
    r = users.post("/api/v1/usuarios", headers=cab(token_admin), json={})
    assert r.status_code == 422
    validar(r.get_json(), "Error")


def test_documento_cumple_su_esquema(documentos, token_auditor):
    creado = documentos.post("/api/v1/documentos", headers=cab(token_auditor), json={
        "tipo": "AVISO_PRIVACIDAD",
        "contenido": {"version": "v1", "texto": "aviso de prueba"}})
    assert creado.status_code == 201
    doc_id = creado.get_json()["documento_id"]
    r = documentos.get(f"/api/v1/documentos/{doc_id}", headers=cab(token_auditor))
    validar(r.get_json(), "Documento")


def test_notificacion_cumple_su_esquema(notificaciones, token_especialista,
                                        token_colaborador):
    notificaciones.post("/api/v1/notificaciones", headers=cab(token_especialista),
                        json={"tipo": "CONSENTIMIENTO_POR_VENCER",
                              "titulo": "Tu consentimiento vence pronto",
                              "mensaje": "Revisa tu consentimiento en el portal.",
                              "destinatarios": ["USR-00001"]})
    r = notificaciones.get("/api/v1/notificaciones/mias", headers=cab(token_colaborador))
    for n in r.get_json()["notificaciones"]:
        validar(n, "Notificacion")


def test_una_solicitud_mal_formada_no_valida():
    """Comprueba que el esquema rechaza de verdad, no solo documenta."""
    v = Draft202012Validator(esquema("SolicitudAlta"))
    assert list(v.iter_errors({"usuario_id": "ABC", "correo": "x"}))
    assert not list(v.iter_errors({
        "usuario_id": "USR-00042", "correo": "a@b.mx", "nombre": "Ana",
        "apellido_paterno": "Lopez", "contrasena": "contrasena-larga",
        "perfil_id": 1}))


def test_los_esquemas_estan_al_dia_con_los_contratos(auth, users):
    """Si alguien edita el OpenAPI y no regenera, esta prueba lo detecta."""
    import subprocess
    import sys
    raiz = os.path.dirname(JSON_DIR.rstrip("/").rsplit("/contratos", 1)[0])
    antes = {}
    for a in os.listdir(JSON_DIR):
        with open(os.path.join(JSON_DIR, a), encoding="utf8") as f:
            antes[a] = f.read()

    subprocess.run([sys.executable,
                    os.path.join(JSON_DIR, "..", "generar_json.py")],
                   check=True, capture_output=True,
                   cwd=os.path.join(JSON_DIR, "..", ".."))

    for a, contenido in antes.items():
        with open(os.path.join(JSON_DIR, a), encoding="utf8") as f:
            assert f.read() == contenido, \
                f"{a} quedo desactualizado: ejecuta contratos/generar_json.py"
