"""Configuración local de URLs y ruta de las cookies de sesión.

En Windows se guarda en %APPDATA%\\LibreriaPython.
En Linux, en ~/.config/libreria-python.
No guarda contraseñas.
"""
import json
import os
from pathlib import Path

DEFAULT_LOGIN_URL = "http://localhost:5000"
DEFAULT_BOOKS_URL = "http://localhost:5001"


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


def defaults():
    return {
        "loginUrl": normalize_url(os.environ.get("LIBRERIA_LOGIN_URL"), DEFAULT_LOGIN_URL),
        "booksUrl": normalize_url(os.environ.get("LIBRERIA_BOOKS_URL"), DEFAULT_BOOKS_URL),
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
    if stored.get("loginUrl"):
        data["loginUrl"] = normalize_url(stored["loginUrl"], DEFAULT_LOGIN_URL)
    if stored.get("booksUrl"):
        data["booksUrl"] = normalize_url(stored["booksUrl"], DEFAULT_BOOKS_URL)
    return data


def save(login_url, books_url):
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "loginUrl": normalize_url(login_url, DEFAULT_LOGIN_URL),
        "booksUrl": normalize_url(books_url, DEFAULT_BOOKS_URL),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def restore_defaults():
    path = config_path()
    if path.is_file():
        path.unlink()
    payload = {
        "loginUrl": DEFAULT_LOGIN_URL,
        "booksUrl": DEFAULT_BOOKS_URL,
    }
    return save(payload["loginUrl"], payload["booksUrl"])
