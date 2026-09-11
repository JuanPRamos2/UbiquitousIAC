import logging
from xml.etree import ElementTree as ET

from config.settings import SOAP_NS, TNS
from soap.envelope import serialize

logger = logging.getLogger(__name__)

FAULT_CLIENT = "soap:Client"
FAULT_SERVER = "soap:Server"


class SoapFault(Exception):
    def __init__(self, faultstring, faultcode=FAULT_CLIENT, http_status=400, detail_code=None, detail_name="ServiceFault"):
        super().__init__(faultstring)
        self.faultstring = faultstring
        self.faultcode = faultcode
        self.http_status = http_status
        self.detail_code = detail_code if detail_code is not None else http_status
        self.detail_name = detail_name

    def to_xml(self):
        ET.register_namespace("soap", SOAP_NS)
        ET.register_namespace("tns", TNS)
        envelope = ET.Element(f"{{{SOAP_NS}}}Envelope")
        ET.SubElement(envelope, f"{{{SOAP_NS}}}Header")
        body = ET.SubElement(envelope, f"{{{SOAP_NS}}}Body")
        fault = ET.SubElement(body, f"{{{SOAP_NS}}}Fault")
        code = ET.SubElement(fault, "faultcode")
        code.text = self.faultcode
        message = ET.SubElement(fault, "faultstring")
        message.text = self.faultstring
        detail = ET.SubElement(fault, "detail")
        payload = ET.SubElement(detail, f"{{{TNS}}}{self.detail_name}")
        codigo = ET.SubElement(payload, f"{{{TNS}}}codigo")
        codigo.text = str(self.detail_code)
        texto = ET.SubElement(payload, f"{{{TNS}}}mensaje")
        texto.text = self.faultstring
        return serialize(envelope)


def client_fault(message, http_status=400, detail_name="ClientFault"):
    return SoapFault(message, FAULT_CLIENT, http_status, http_status, detail_name)


def duplicate_fault():
    return SoapFault(
        "El concepto ya fue clasificado por este usuario",
        FAULT_CLIENT,
        409,
        409,
        "DuplicadoFault",
    )


def server_fault():
    logger.exception("Falla interna; el cliente recibe un Fault genérico")
    return SoapFault(
        "El servicio no pudo completar la operación. Intenta de nuevo más tarde.",
        FAULT_SERVER,
        500,
        500,
        "ServerFault",
    )


def unauthorized_fault():
    return SoapFault(
        "Credenciales WS-Security inválidas o ausentes",
        FAULT_CLIENT,
        401,
        401,
        "SecurityFault",
    )
