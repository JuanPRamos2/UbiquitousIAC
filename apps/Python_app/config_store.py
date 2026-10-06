"""Configuración local de URLs y ruta de las cookies de sesión.

En Windows se guarda en %APPDATA%\\LibreriaPython.
En Linux, en ~/.config/libreria-python.
No guarda contraseñas.
"""
import json
import os
from pathlib import Path

DEFAULT_SCHEME = "http"
DEFAULT_LOGIN_URL = "http://localhost:5000"
DEFAULT_BOOKS_URL = "http://localhost:5001"
DEFAULT_USERS_URL = "http://localhost:5002"
DEFAULT_AUTHORS_URL = "http://localhost:5003"
DEFAULT_PEDIDOS_URL = "http://localhost:5004"
DEFAULT_PAGOS_URL = "http://localhost:5005"


def directory():
    override = os.environ.get("LIBRERIA_PYTHON_HOME", "").strip()
    if override:
        return Path(override)
    if os.name == "nt":
        root = os.environ.get("APPDATA") or str(Path.home())
        return Path(root) / "LibreriaPython"
    return Path.home() / ".config" / "libreria-python"


def config_path():
    return directory() / "config.json"


def cookie_path():
    return directory() / "session-cookies.txt"


def token_path():
    return directory() / "jwt.txt"


def normalize_url(value, default):
    raw = (value or "").strip() or default
    return raw.rstrip("/")


def with_scheme(url, scheme):
    rest = url.split("://", 1)[1] if "://" in (url or "") else (url or "")
    return f"{scheme}://{rest}".rstrip("/")


def defaults():
    scheme = os.environ.get("LIBRERIA_SCHEME", DEFAULT_SCHEME).strip().lower() or DEFAULT_SCHEME
    if scheme not in ("http", "https"):
        scheme = DEFAULT_SCHEME
    return {
        "scheme": scheme,
        "loginUrl": normalize_url(os.environ.get("LIBRERIA_LOGIN_URL"), DEFAULT_LOGIN_URL),
        "booksUrl": normalize_url(os.environ.get("LIBRERIA_BOOKS_URL"), DEFAULT_BOOKS_URL),
        "usersUrl": normalize_url(os.environ.get("LIBRERIA_USERS_URL"), DEFAULT_USERS_URL),
        "authorsUrl": normalize_url(os.environ.get("LIBRERIA_AUTHORS_URL"), DEFAULT_AUTHORS_URL),
        "pedidosUrl": normalize_url(os.environ.get("LIBRERIA_PEDIDOS_URL"), DEFAULT_PEDIDOS_URL),
        "pagosUrl": normalize_url(os.environ.get("LIBRERIA_PAGOS_URL"), DEFAULT_PAGOS_URL),
    }


def load():
    data = defaults()
    path = config_path()
    if not path.is_file():
        return data
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return data
    if not isinstance(stored, dict):
        return data
    scheme = str(stored.get("scheme") or "").strip().lower()
    if scheme in ("http", "https"):
        data["scheme"] = scheme
    for key, default in (
        ("loginUrl", DEFAULT_LOGIN_URL),
        ("booksUrl", DEFAULT_BOOKS_URL),
        ("usersUrl", DEFAULT_USERS_URL),
        ("authorsUrl", DEFAULT_AUTHORS_URL),
        ("pedidosUrl", DEFAULT_PEDIDOS_URL),
        ("pagosUrl", DEFAULT_PAGOS_URL),
    ):
        if stored.get(key):
            data[key] = normalize_url(stored[key], default)
    return data


def save(login_url, books_url, **extra):
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = load()
    payload["loginUrl"] = normalize_url(login_url, DEFAULT_LOGIN_URL)
    payload["booksUrl"] = normalize_url(books_url, DEFAULT_BOOKS_URL)
    for key, value in extra.items():
        if key == "scheme":
            scheme = str(value or "").strip().lower()
            if scheme in ("http", "https"):
                payload["scheme"] = scheme
            continue
        if key.endswith("Url"):
            payload[key] = normalize_url(value, payload.get(key, ""))
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def restore_defaults():
    path = config_path()
    if path.is_file():
        path.unlink()
    fresh = defaults()
    fresh["scheme"] = DEFAULT_SCHEME
    fresh["loginUrl"] = DEFAULT_LOGIN_URL
    fresh["booksUrl"] = DEFAULT_BOOKS_URL
    fresh["usersUrl"] = DEFAULT_USERS_URL
    fresh["authorsUrl"] = DEFAULT_AUTHORS_URL
    fresh["pedidosUrl"] = DEFAULT_PEDIDOS_URL
    fresh["pagosUrl"] = DEFAULT_PAGOS_URL
    return save(
        fresh["loginUrl"],
        fresh["booksUrl"],
        scheme=fresh["scheme"],
        usersUrl=fresh["usersUrl"],
        authorsUrl=fresh["authorsUrl"],
        pedidosUrl=fresh["pedidosUrl"],
        pagosUrl=fresh["pagosUrl"],
    )
