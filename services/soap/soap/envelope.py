from xml.etree import ElementTree as ET

from config.settings import SOAP_NS, TNS

SOAP = SOAP_NS
NSMAP_PREFIXES = {
    "soap": SOAP_NS,
    "tns": TNS,
}


def local_name(tag):
    if tag is None:
        return ""
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def find_child(parent, name):
    if parent is None:
        return None
    for child in list(parent):
        if local_name(child.tag) == name:
            return child
    return None


def find_all(parent, name):
    if parent is None:
        return []
    return [child for child in list(parent) if local_name(child.tag) == name]


def text_of(parent, name, default=""):
    node = find_child(parent, name)
    if node is None or node.text is None:
        return default
    return node.text.strip()


def parse_envelope(xml_bytes):
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError("El documento XML no es un Envelope SOAP válido") from exc
    if local_name(root.tag) != "Envelope":
        raise ValueError("La raíz del documento debe ser soap:Envelope")
    header = find_child(root, "Header")
    body = find_child(root, "Body")
    if body is None:
        raise ValueError("El Envelope no contiene soap:Body")
    return root, header, body


def body_operation(body):
    for child in list(body):
        if local_name(child.tag) != "Fault":
            return child
    return None


def _element(parent, ns, tag, text=None):
    node = ET.SubElement(parent, f"{{{ns}}}{tag}")
    if text is not None:
        node.text = str(text)
    return node


def build_envelope(body_builder, header_builder=None):
    ET.register_namespace("soap", SOAP_NS)
    ET.register_namespace("tns", TNS)
    envelope = ET.Element(f"{{{SOAP_NS}}}Envelope")
    header = ET.SubElement(envelope, f"{{{SOAP_NS}}}Header")
    if header_builder is not None:
        header_builder(header)
    body = ET.SubElement(envelope, f"{{{SOAP_NS}}}Body")
    body_builder(body)
    return serialize(envelope)


def build_response(operation_name, fields, extra_children=None):
    def body_builder(body):
        response = _element(body, TNS, operation_name + "Response")
        for name, value in fields:
            _element(response, TNS, name, value)
        if extra_children:
            extra_children(response)

    return build_envelope(body_builder)


def serialize(element):
    xml = ET.tostring(element, encoding="utf-8", xml_declaration=True, method="xml")
    return xml
