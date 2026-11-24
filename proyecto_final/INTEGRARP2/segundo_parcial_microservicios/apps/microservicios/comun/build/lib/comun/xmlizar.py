"""
Serialización a XML.

El requisito pide que los microservicios respondan en JSON y en XML. En
lugar de escribir dos veces cada respuesta, cada endpoint arma un
diccionario y esta capa lo convierte al formato que el cliente pidió.

Reglas de la conversión, pensadas para que el XSD pueda describirlas:

  - Cada clave del diccionario es un elemento.
  - Una lista se envuelve en un elemento plural que contiene elementos en
    singular. Por ejemplo {"usuarios": [...]} produce
    <usuarios><usuario>...</usuario></usuarios>. Sin esa envoltura, un
    esquema no puede distinguir una lista de un elemento repetido.
  - None se representa con xsi:nil="true" y no con una cadena vacía: la
    diferencia entre "no hay dato" y "el dato es vacío" importa, por
    ejemplo en un valor agregado suprimido por el umbral.
  - Los numeros y booleanos se escriben en su forma canonica de XML
    Schema (true/false en minuscula), no en la de Python.
"""
import datetime
import decimal
import re
import xml.etree.ElementTree as ET

ESPACIO = "http://nexum.com.mx/bienestar/v1"
XSI = "http://www.w3.org/2001/XMLSchema-instance"

# Plural -> singular, para nombrar los elementos hijos de una lista.
SINGULARES = {
    "usuarios": "usuario", "perfiles": "perfil", "permisos": "permiso",
    "documentos": "documento", "notificaciones": "notificacion",
    "detalles": "detalle", "elementos": "elemento", "evidencias": "evidencia",
    "campanias": "campania", "unidades": "unidad", "destinatarios": "destinatario",
}


def _singular(plural: str) -> str:
    if plural in SINGULARES:
        return SINGULARES[plural]
    if plural.endswith("es") and len(plural) > 3:
        return plural[:-2]
    if plural.endswith("s") and len(plural) > 2:
        return plural[:-1]
    return "elemento"


def _texto(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return format(v, "f")
    return str(v)


def _nombre_valido(k: str) -> str:
    """Un nombre de elemento XML no puede empezar con digito ni traer espacios."""
    n = re.sub(r"[^\w.-]", "_", str(k))
    return n if re.match(r"^[A-Za-z_]", n) else f"_{n}"


def _poblar(padre: ET.Element, clave: str, valor):
    if isinstance(valor, dict):
        hijo = ET.SubElement(padre, _nombre_valido(clave))
        for k, v in valor.items():
            _poblar(hijo, k, v)
    elif isinstance(valor, (list, tuple)):
        envoltura = ET.SubElement(padre, _nombre_valido(clave))
        singular = _singular(str(clave))
        for item in valor:
            if isinstance(item, dict):
                hijo = ET.SubElement(envoltura, singular)
                for k, v in item.items():
                    _poblar(hijo, k, v)
            else:
                ET.SubElement(envoltura, singular).text = _texto(item)
    elif valor is None:
        hijo = ET.SubElement(padre, _nombre_valido(clave))
        hijo.set(f"{{{XSI}}}nil", "true")
    else:
        ET.SubElement(padre, _nombre_valido(clave)).text = _texto(valor)


def a_xml(datos: dict, raiz: str = "respuesta") -> str:
    ET.register_namespace("", ESPACIO)
    ET.register_namespace("xsi", XSI)
    root = ET.Element(f"{{{ESPACIO}}}{raiz}")
    root.set(f"{{{XSI}}}schemaLocation", f"{ESPACIO} {raiz}.xsd")
    for k, v in datos.items():
        _poblar(root, k, v)
    ET.indent(root, space="  ")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            + ET.tostring(root, encoding="unicode"))
