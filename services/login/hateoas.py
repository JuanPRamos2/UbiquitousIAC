from flask import request


def _url(path, fmt=None):
    base = request.url_root.rstrip("/")
    href = f"{base}{path}"
    if fmt:
        href = f"{href}?format={fmt}"
    return href


def links_for(*rels, extra=None):
    fmt = "json" if (request.args.get("format") or "").strip().lower() == "json" else None
    catalog = {
        "self": {"href": request.url, "method": request.method},
        "register": {"href": _url("/register", fmt), "method": "GET"},
        "login": {"href": _url("/login", fmt), "method": "GET"},
        "logout": {"href": _url("/logout", fmt), "method": "GET"},
        "session": {"href": _url("/session", fmt), "method": "GET"},
        "extend": {"href": _url("/session", fmt), "method": "POST"},
        "health": {"href": _url("/health", fmt), "method": "GET"},
        "captcha": {"href": _url("/captcha", fmt), "method": "GET"},
        "verify": {"href": _url("/verify-email", fmt), "method": "GET"},
        "account": {"href": _url("/account", fmt), "method": "GET"},
        "docs": {"href": _url("/docs"), "method": "GET"},
        "ui": {"href": _url("/ui"), "method": "GET"},
        "openapi": {"href": _url("/openapi.yaml"), "method": "GET"},
    }
    selected = {rel: catalog[rel] for rel in rels if rel in catalog}
    if extra:
        selected.update(extra)
    return selected
