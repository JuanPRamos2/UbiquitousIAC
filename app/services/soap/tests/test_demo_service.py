import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["SOAP_DEMO"] = "1"
os.environ["SOAP_STATS_PASSWORD_HASH"] = ""

from db.demo_store import reset
from soap.security import verify_password
from config import settings
from app import app


def setup_function():
    reset()


def test_demo_mode_is_on():
    assert settings.SOAP_DEMO is True
    assert verify_password("laboratorio", settings.SOAP_STATS_PASSWORD_HASH)


def test_pendientes_and_registrar():
    client = app.test_client()
    request_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:tns="http://udem.edu.mx/iac/library-classifier">
      <soap:Body>
        <tns:RegistrarClasificacion>
          <tns:nombre>Juan Pablo</tns:nombre>
          <tns:apellidos>Ramos Salazar</tns:apellidos>
          <tns:correo>juan.pablo@udem.edu</tns:correo>
          <tns:conceptId>101</tns:conceptId>
          <tns:isbn>9780134444245</tns:isbn>
          <tns:modelo>IaaS</tns:modelo>
          <tns:tipoCliente>desktop-web</tns:tipoCliente>
        </tns:RegistrarClasificacion>
      </soap:Body>
    </soap:Envelope>
    """
    first = client.post("/soap", data=request_xml, content_type="text/xml")
    assert first.status_code == 200
    assert "Clasificación registrada".encode("utf-8") in first.data
    second = client.post("/soap", data=request_xml, content_type="text/xml")
    assert second.status_code == 409
    assert b"DuplicadoFault" in second.data
    assert b"409" in second.data


def test_invalid_xml():
    client = app.test_client()
    response = client.post("/soap", data=b"<not-xml", content_type="text/xml")
    assert response.status_code == 400
    assert b"soap:Fault" in response.data


def test_stats_requires_ws_security():
    client = app.test_client()
    bare = """<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:tns="http://udem.edu.mx/iac/library-classifier">
      <soap:Header/>
      <soap:Body>
        <tns:ObtenerEstadisticasPorModelo/>
      </soap:Body>
    </soap:Envelope>
    """
    denied = client.post("/soap", data=bare, content_type="text/xml")
    assert denied.status_code == 401

    ok = """<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:tns="http://udem.edu.mx/iac/library-classifier"
                   xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <soap:Header>
        <wsse:Security>
          <wsse:UsernameToken>
            <wsse:Username>soap_stats</wsse:Username>
            <wsse:Password>laboratorio</wsse:Password>
          </wsse:UsernameToken>
        </wsse:Security>
      </soap:Header>
      <soap:Body>
        <tns:ObtenerEstadisticasPorModelo/>
      </soap:Body>
    </soap:Envelope>
    """
    allowed = client.post("/soap", data=ok, content_type="text/xml")
    assert allowed.status_code == 200
    assert b"ObtenerEstadisticasPorModeloResponse" in allowed.data


def test_probar_page_is_served():
    client = app.test_client()
    page = client.get("/")
    assert page.status_code == 200
    assert "Probar el módulo SOAP".encode("utf-8") in page.data
    assert b'data-soap-endpoint="/soap"' in page.data
