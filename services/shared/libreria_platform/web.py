"""CORS y respuestas HTTP comunes. Cada servicio sigue teniendo sus rutas."""
import os

from flask import jsonify

from libreria_platform.jwt_tokens import TokenError, is_admin, read_access_token

DEFAULT_ORIGINS = ",".join(
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
    ]
)


def allowed_origins():
    raw = os.getenv("CORS_ORIGINS", DEFAULT_ORIGINS)
    return [item.strip() for item in raw.split(",") if item.strip()]


def apply_cors(app):
    from flask_cors import CORS

    CORS(
        app,
        origins=allowed_origins(),
        supports_credentials=True,
    )


def error(message, status, code):
    return jsonify({"ok": False, "error": message, "errors": [message], "code": code}), status


def token_status(exc):
    if exc.code == "REDIS_UNAVAILABLE":
        return 503
    return 401


def require_bearer(password_fallback, admin=False):
    try:
        claims = read_access_token(
            __import__("flask").request.headers.get("Authorization"),
            password_fallback,
        )
    except TokenError as exc:
        return None, error(exc.message, token_status(exc), exc.code)
    if admin and not is_admin(claims):
        return None, error("Rol insuficiente para esta operación.", 403, "FORBIDDEN")
    return claims, None
