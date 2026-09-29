"""JWT emitido por este microservicio (login) y compartido con books.

La contraseña compartida JWT_PASSWORD es la misma en ambos servicios.
La clave HMAC es su hash SHA-256. PyJWT firma y verifica con HS256.
El hash de la contraseña del usuario sigue en PostgreSQL (bcrypt) y no se usa para firmar.
"""
import hashlib
from datetime import datetime, timedelta, timezone

import jwt

import config


class TokenError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


def signing_key():
    return hashlib.sha256(config.JWT_PASSWORD.encode("utf-8")).hexdigest()


def issue_token(user):
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=config.JWT_MINUTES)
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user.get("role") or "",
        "iss": config.JWT_ISSUER,
        "aud": config.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    token = jwt.encode(payload, signing_key(), algorithm="HS256")
    return token, expires


def read_bearer(header):
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
    try:
        return jwt.decode(
            parts[1],
            signing_key(),
            algorithms=["HS256"],
            issuer=config.JWT_ISSUER,
            audience=config.JWT_AUDIENCE,
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError(
            "El token JWT ya expiró. Vuelve a iniciar sesión en el servicio de login.",
            "TOKEN_EXPIRED",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError(
            "El token JWT es inválido o no fue emitido por el servicio de login.",
            "TOKEN_INVALID",
        ) from exc
