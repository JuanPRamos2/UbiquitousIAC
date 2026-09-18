import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from soap.envelope import parse_envelope, local_name
from soap.faults import duplicate_fault, client_fault
from soap.security import hash_password, verify_password


def test_parse_envelope_identifies_operation():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:tns="http://udem.edu.mx/iac/library-classifier">
      <soap:Body>
        <tns:RegistrarClasificacion>
          <tns:nombre>Ana</tns:nombre>
        </tns:RegistrarClasificacion>
      </soap:Body>
    </soap:Envelope>
    """
    root, header, body = parse_envelope(xml)
    assert local_name(root.tag) == "Envelope"
    assert header is None or local_name(header.tag) == "Header"
    assert local_name(list(body)[0].tag) == "RegistrarClasificacion"


def test_invalid_xml_raises():
    try:
        parse_envelope(b"<not-xml")
        assert False, "debio fallar"
    except ValueError:
        pass


def test_duplicate_fault_contains_409():
    xml = duplicate_fault().to_xml().decode("utf-8")
    assert "409" in xml
    assert "DuplicadoFault" in xml
    assert "ya fue clasificado" in xml
    assert "psycopg2" not in xml.lower()


def test_client_fault_does_not_leak_sql():
    xml = client_fault("El campo modelo es obligatorio").to_xml().decode("utf-8")
    assert "SELECT" not in xml
    assert "soap:Client" in xml


def test_password_hash_is_not_plaintext():
    hashed = hash_password("IacSoapLab2026")
    assert hashed.startswith("pbkdf2_sha256$")
    assert "IacSoapLab2026" not in hashed
    assert verify_password("IacSoapLab2026", hashed)
    assert not verify_password("otra", hashed)
