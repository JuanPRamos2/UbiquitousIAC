"""Serialización XML y detección del parámetro format."""
from xml.etree import ElementTree as ET

from flask import Response, jsonify, request

SINGULAR = {
    "books": "book",
    "concepts": "concept",
    "images": "image",
    "authors": "author",
    "models": "model",
    "endpoints": "endpoint",
    "items": "item",
}


def wants_json():
    """JSON sólo si llega format=json (o el alias format-json). Sin parámetro: XML."""
    fmt = (request.args.get("format") or "").strip().lower()
    if fmt in ("json", "application/json"):
        return True
    if fmt in ("xml", "application/xml", "text/xml"):
        return False
    if "format-json" in request.args:
        return True
    return False


def _singular(tag):
    if tag in SINGULAR:
        return SINGULAR[tag]
    if tag.endswith("ies"):
        return tag[:-3] + "y"
    if tag.endswith("s") and not tag.endswith("ss"):
        return tag[:-1]
    return tag


def _append(parent, key, value):
    if isinstance(value, list):
        wrapper = ET.SubElement(parent, key)
        child_tag = _singular(key)
        for item in value:
            node = ET.SubElement(wrapper, child_tag)
            if isinstance(item, dict):
                for nested_key, nested_value in item.items():
                    _append(node, str(nested_key), nested_value)
            else:
                node.text = "" if item is None else str(item)
        return
    node = ET.SubElement(parent, str(key))
    if isinstance(value, dict):
        for nested_key, nested_value in value.items():
            _append(node, str(nested_key), nested_value)
        return
    if isinstance(value, bool):
        node.text = "true" if value else "false"
    elif value is None:
        node.text = ""
    else:
        node.text = str(value)


def dict_to_xml(root_tag, payload):
    root = ET.Element(root_tag)
    if isinstance(payload, list):
        child_tag = _singular(root_tag)
        for item in payload:
            node = ET.SubElement(root, child_tag)
            if isinstance(item, dict):
                for key, value in item.items():
                    _append(node, str(key), value)
            else:
                node.text = "" if item is None else str(item)
    elif isinstance(payload, dict):
        for key, value in payload.items():
            _append(root, str(key), value)
    elif payload is not None:
        root.text = str(payload)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def respond(payload, root_tag="response", status=200):
    if wants_json():
        body = payload
        if isinstance(payload, dict) and "format" not in payload:
            body = {"format": "json", **payload}
        return jsonify(body), status
    xml = dict_to_xml(root_tag, payload)
    return Response(xml, status=status, mimetype="application/xml; charset=utf-8")
