"""
Validación de las respuestas XML contra los esquemas XSD.

Un XSD que nadie comprueba contra respuestas reales es documentación que
se desactualiza en silencio. Estas pruebas toman la salida real de cada
microservicio y la validan con lxml: si alguien cambia un campo sin
actualizar el esquema, la prueba falla.
"""
import os

import pytest
from conftest import cab
from lxml import etree

XSD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "contratos", "xml")


def esquema(nombre):
    # El esquema se parsea desde su carpeta para que xs:include resuelva.
    return etree.XMLSchema(etree.parse(os.path.join(XSD, nombre)))


def validar(xml_bytes, nombre_xsd):
    esq = esquema(nombre_xsd)
    doc = etree.fromstring(xml_bytes)
    if not esq.validate(doc):
        pytest.fail(f"La respuesta no cumple {nombre_xsd}:\n" +
                    "\n".join(str(e) for e in esq.error_log))
    return doc


def test_los_cinco_esquemas_compilan():
    for n in ("comun.xsd", "sesion.xsd", "usuarios.xsd",
              "documentos.xsd", "notificaciones.xsd"):
        assert esquema(n) is not None


def test_sesion_cumple_su_esquema(auth):
    r = auth.post("/api/v1/auth/login?formato=xml",
                  json={"correo": "roberto.garcia@nexum.com.mx",
                        "contrasena": "demo123"})
    assert r.status_code == 200
    validar(r.get_data(), "sesion.xsd")


def test_validacion_cumple_su_esquema(auth, token_admin):
    r = auth.get("/api/v1/auth/validar", headers=cab(token_admin, xml=True))
    assert r.status_code == 200
    validar(r.get_data(), "sesion.xsd")


def test_listado_de_usuarios_cumple_su_esquema(users, token_admin):
    r = users.get("/api/v1/usuarios?tamano=5", headers=cab(token_admin, xml=True))
    assert r.status_code == 200
    doc = validar(r.get_data(), "usuarios.xsd")
    ns = {"b": "http://nexum.com.mx/bienestar/v1"}
    assert doc.find("b:paginacion/b:total", ns) is not None


def test_el_error_cumple_el_esquema_comun(users, token_colaborador):
    r = users.get("/api/v1/usuarios", headers=cab(token_colaborador, xml=True))
    assert r.status_code == 403
    validar(r.get_data(), "comun.xsd")


def test_error_de_validacion_con_detalles_cumple_el_esquema(users, token_admin):
    r = users.post("/api/v1/usuarios?formato=xml", headers=cab(token_admin),
                   json={"usuario_id": "malo"})
    assert r.status_code == 422
    doc = validar(r.get_data(), "comun.xsd")
    ns = {"b": "http://nexum.com.mx/bienestar/v1"}
    assert doc.findall(".//b:detalles/b:detalle", ns)


def test_documentos_cumplen_su_esquema(documentos, token_auditor):
    documentos.post("/api/v1/documentos", headers=cab(token_auditor), json={
        "tipo": "EVIDENCIA_CONSENTIMIENTO", "seudonimo_id": "SEUD-00002",
        "contenido": {"version_aviso": "AVISO-v1", "decision": "ACEPTADO"}})
    r = documentos.get("/api/v1/documentos?tamano=3",
                       headers=cab(token_auditor, xml=True))
    assert r.status_code == 200
    validar(r.get_data(), "documentos.xsd")


def test_notificaciones_cumplen_su_esquema(notificaciones, token_especialista,
                                           token_colaborador):
    notificaciones.post("/api/v1/notificaciones", headers=cab(token_especialista),
                        json={"tipo": "PLAN_APROBADO",
                              "titulo": "Se aprobo un plan",
                              "mensaje": "Hay un plan de intervencion aprobado en tu unidad",
                              "destinatarios": ["USR-00001"]})
    r = notificaciones.get("/api/v1/notificaciones/mias",
                           headers=cab(token_colaborador, xml=True))
    assert r.status_code == 200
    validar(r.get_data(), "notificaciones.xsd")


def test_un_identificador_mal_formado_no_valida():
    """Comprueba que el patrón del XSD realmente rechaza, no solo decora."""
    esq = esquema("usuarios.xsd")
    malo = """<?xml version="1.0" encoding="UTF-8"?>
<usuario_respuesta xmlns="http://nexum.com.mx/bienestar/v1">
  <usuario_id>ABC-1</usuario_id>
  <nombre>X</nombre><apellido_paterno>Y</apellido_paterno>
  <correo>no-es-correo</correo><activo>true</activo>
  <perfil_id>1</perfil_id><perfil>Colaborador</perfil>
  <unidad_alcance_id xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:nil="true"/>
</usuario_respuesta>"""
    assert not esq.validate(etree.fromstring(malo.encode()))


def test_el_esquema_de_documentos_no_admite_identificador_de_empleado():
    """La separacion de identidad queda escrita tambien en el contrato."""
    esq = esquema("documentos.xsd")
    malo = """<?xml version="1.0" encoding="UTF-8"?>
<documento_respuesta xmlns="http://nexum.com.mx/bienestar/v1">
  <documento_id>DOC-0123456789AB</documento_id>
  <tipo>EVIDENCIA_CONSENTIMIENTO</tipo>
  <version>1</version>
  <empleado_id>EMP-00001</empleado_id>
  <contenido/>
  <hash_contenido>0000000000000000000000000000000000000000000000000000000000000000</hash_contenido>
  <fecha_creacion>2026-10-13T00:00:00+00:00</fecha_creacion>
</documento_respuesta>"""
    assert not esq.validate(etree.fromstring(malo.encode()))
