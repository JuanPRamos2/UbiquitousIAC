"""Firma y verificación HS256 compartidas por todos los microservicios.

La clave sale de JWT_SECRET_KEY. Si esa variable no está, se usa el hash
SHA-256 de JWT_PASSWORD para no romper un entorno que ya firmaba así.
Ninguna de las dos se escribe como valor fijo en este módulo.
"""
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from libreria_platform.redis_store import RedisUnavailable, store

ISSUER = "login"
AUDIENCE = "libreria"
ALGORITHM = "HS256"


class TokenError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


def signing_key(password_fallback):
    explicit = os.getenv("JWT_SECRET_KEY", "").strip()
    if explicit:
        return explicit
    if not password_fallback:
        raise TokenError("Falta JWT_SECRET_KEY.", "TOKEN_INVALID")
    return hashlib.sha256(password_fallback.encode("utf-8")).hexdigest()


def issue_access_token(user, minutes, password_fallback):
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=int(minutes))
    jti = str(uuid.uuid4())
    role_id = user.get("role_id")
    payload = {
        "sub": str(user["id"]),
        "user_id": int(user["id"]),
        "email": user.get("email") or "",
        "role": user.get("role") or "",
        "role_id": int(role_id or 0),
        "jti": jti,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    token = jwt.encode(payload, signing_key(password_fallback), algorithm=ALGORITHM)
    return token, expires, jti


def _decode(token, password_fallback, verify_exp=True):
    return jwt.decode(
        token,
        signing_key(password_fallback),
        algorithms=[ALGORITHM],
        issuer=ISSUER,
        audience=AUDIENCE,
        options={"verify_exp": verify_exp},
    )


def _bearer_token(header):
    if not header or not str(header).strip():
        raise TokenError(
            "Falta el encabezado Authorization. Envía Authorization: Bearer <token>.",
            "TOKEN_MISSING",
        )
    parts = str(header).strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise TokenError(
            "El encabezado Authorization debe usar el esquema Bearer.",
            "TOKEN_MALFORMED",
        )
    return parts[1]


def _require_claims(claims):
    if not claims.get("jti"):
        raise TokenError("El token no incluye jti.", "TOKEN_INVALID")
    if claims.get("user_id") in (None, ""):
        raise TokenError("El token no incluye user_id.", "TOKEN_INVALID")
    if claims.get("role_id") in (None, ""):
        raise TokenError("El token no incluye role_id.", "TOKEN_INVALID")


def assert_not_revoked(claims):
    jti = claims.get("jti")
    if not jti:
        raise TokenError("El token no incluye jti.", "TOKEN_INVALID")
    try:
        revoked = store.get(f"jwt:revoked:{jti}")
    except RedisUnavailable as exc:
        raise TokenError(
            "No se puede autorizar la petición porque Redis no está disponible.",
            "REDIS_UNAVAILABLE",
        ) from exc
    if revoked:
        raise TokenError(
            "El token fue revocado. Vuelve a iniciar sesión.",
            "TOKEN_REVOKED",
        )


def read_access_token(header, password_fallback):
    token = _bearer_token(header)
    try:
        claims = _decode(token, password_fallback, verify_exp=True)
    except jwt.ExpiredSignatureError as exc:
        raise TokenError(
            "El token JWT ya expiró. Renóvalo o vuelve a iniciar sesión.",
            "TOKEN_EXPIRED",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError(
            "El token JWT es inválido o no fue emitido por el servicio de login.",
            "TOKEN_INVALID",
        ) from exc
    _require_claims(claims)
    assert_not_revoked(claims)
    return claims


def peek_access_token(header, password_fallback):
    """Lee un Bearer aunque ya haya expirado. Sirve para revocarlo en /logout."""
    token = _bearer_token(header)
    try:
        claims = _decode(token, password_fallback, verify_exp=False)
    except jwt.InvalidTokenError as exc:
        raise TokenError(
            "El token JWT es inválido o no fue emitido por el servicio de login.",
            "TOKEN_INVALID",
        ) from exc
    return claims


def is_admin(claims):
    try:
        if int(claims.get("role_id") or 0) == 1:
            return True
    except (TypeError, ValueError):
        pass
    return str(claims.get("role") or "").lower() == "admin"


def revoke(jti, expires_at_epoch):
    if not jti:
        return
    now = int(datetime.now(timezone.utc).timestamp())
    try:
        remaining = int(expires_at_epoch) - now
    except (TypeError, ValueError):
        remaining = 60
    ttl = remaining if remaining > 0 else 60
    store.setex(f"jwt:revoked:{jti}", ttl, "1")
