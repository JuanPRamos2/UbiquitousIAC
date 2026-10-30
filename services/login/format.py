from xml.etree import ElementTree as ET

from flask import Response, jsonify, request

SINGULAR = {
    "links": "link",
    "items": "item",
    "errors": "error",
}


def wants_json():
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
    if key in ("_links", "links") and isinstance(value, dict):
        wrapper = ET.SubElement(parent, "links")
        for rel, info in value.items():
            node = ET.SubElement(wrapper, "link")
            node.set("rel", rel)
            if isinstance(info, dict):
                if info.get("href"):
                    node.set("href", str(info["href"]))
                if info.get("method"):
                    node.set("method", str(info["method"]))
            else:
                node.set("href", str(info))
        return
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
    if isinstance(payload, dict):
        for key, value in payload.items():
            _append(root, str(key), value)
    elif payload is not None:
        root.text = str(payload)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def respond(payload, root_tag="response", status=200):
    body = payload
    if isinstance(payload, dict) and "format" not in payload:
        body = {"format": "json" if wants_json() else "xml", **payload}
    if wants_json():
        return jsonify(body), status
    return Response(
        dict_to_xml(root_tag, body),
        status=status,
        mimetype="application/xml; charset=utf-8",
    )
