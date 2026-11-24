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
# La tabla es la MISMA que comun-node/src/xmlizar.js. Tiene que serlo: los
# XSD de contratos/xml describen las respuestas de los servicios en Python y
# en Node a la vez, de modo que si un lado envolviera la lista con otro
# nombre de hijo, el mismo esquema no podria validar las dos.
#
# Las excepciones se declaran en lugar de afinar la regla morfologica. La
# regla de "-es" convierte "fuentes" en "fuent" y "reportes" en "report";
# una regla mas lista fallaria en otra palabra y seria mas dificil de
# depurar que una tabla que se lee de un golpe.
SINGULARES = {
    "usuarios": "usuario", "perfiles": "perfil", "permisos": "permiso",
    "documentos": "documento", "notificaciones": "notificacion",
    "detalles": "detalle", "elementos": "elemento", "evidencias": "evidencia",
    "campanias": "campania", "unidades": "unidad", "destinatarios": "destinatario",
    "instrumentos": "instrumento", "reactivos": "reactivo", "versiones": "version",
    "solicitudes": "solicitud", "respuestas": "respuesta", "eventos": "evento",
    "historial": "entrada", "agregados": "agregado", "dimensiones": "dimension",
    "valores": "valor", "reportes": "reporte", "consultas": "consulta",
    "series": "serie", "puntos": "punto", "intervenciones": "intervencion",
    "indices": "indice", "archivos": "archivo", "servicios": "servicio",
    "fuentes": "fuente", "filas": "fila", "celdas": "celda",
    "columnas": "columna", "formatos": "formato", "entradas": "entrada",
    # Los compuestos hay que declararlos: la regla automatica le quita la
    # "s" a la ULTIMA palabra y deja "intervenciones_sugerida", que no es
    # el singular de nada. El error no rompe nada visible, pero produce un
    # XML que no cumple el XSD, y eso lo descubre el cliente y no el
    # servicio.
    "intervenciones_sugeridas": "intervencion_sugerida",
    "reglas": "regla", "detecciones": "deteccion", "corridas": "corrida",
    "no_evaluables": "no_evaluable", "advertencias": "advertencia",
    "acciones": "accion", "lecturas": "lectura", "supresiones": "supresion",
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


# ===========================================================================
# De XML a diccionario: el camino de entrada.
#
# Hasta aquí este módulo solo convertía diccionarios a XML, es decir las
# respuestas. Faltaba el otro sentido, y su ausencia tenía una consecuencia
# concreta: los servicios leían el cuerpo de la petición con
# request.get_json(), de modo que una aplicación cliente que mandara XML
# recibía un 422 por «campos obligatorios» aunque los hubiera mandado
# todos. La aplicación de escritorio del proyecto consume exclusivamente
# XML, así que sin esto esa afirmación no se podía cumplir en las
# operaciones de escritura.
#
# Las reglas son las inversas de la serialización, con una excepción
# deliberada: aquí NO se intenta adivinar tipos. Un <valor>4</valor> se
# entrega como la cadena "4" y no como el entero 4. Adivinar convertiría
# "007" en 7 y "1.0" en 1.0, y la validación de cada servicio ya sabe qué
# tipo espera en cada campo; adivinar aquí solo le quitaría información.
# La única conversión es la de los enteros en los campos que el propio
# servicio pida, y eso lo hace el servicio.
# ===========================================================================

def de_xml(texto: str) -> dict:
    """Convierte el cuerpo XML de una petición en un diccionario.

    Lanza ValueError si el documento no está bien formado, para que el
    servicio responda 400 con un mensaje claro en lugar de 500.
    """
    try:
        raiz = ET.fromstring(texto)
    except ET.ParseError as e:
        raise ValueError(f"El cuerpo no es XML bien formado: {e}")
    return _de_nodo(raiz)


def _sin_espacio(etiqueta: str) -> str:
    return etiqueta.split("}", 1)[-1] if "}" in etiqueta else etiqueta


def _de_nodo(nodo):
    hijos = list(nodo)
    if not hijos:
        if nodo.get(f"{{{XSI}}}nil") == "true":
            return None
        return nodo.text if nodo.text is not None else ""

    # Una envoltura plural cuyos hijos se llaman todos igual es una lista:
    # <valores><valor/><valor/></valores> produce una lista, no un
    # diccionario con una sola clave repetida.
    nombres = [_sin_espacio(h.tag) for h in hijos]
    if len(set(nombres)) == 1 and len(hijos) > 1:
        return [_de_nodo(h) for h in hijos]

    salida = {}
    for hijo in hijos:
        nombre = _sin_espacio(hijo.tag)
        valor = _de_nodo(hijo)
        if nombre in salida:
            if not isinstance(salida[nombre], list):
                salida[nombre] = [salida[nombre]]
            salida[nombre].append(valor)
        else:
            salida[nombre] = valor
    return salida
