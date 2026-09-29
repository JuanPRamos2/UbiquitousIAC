"""Verifica el JWT que emite el microservicio de login.

Este servicio no crea tokens. La contraseña compartida JWT_PASSWORD y su
hash SHA-256 tienen que coincidir con apps/services/login.
"""
import hashlib

import jwt

from config import settings


class TokenError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


def signing_key():
    return hashlib.sha256(settings.JWT_PASSWORD.encode("utf-8")).hexdigest()


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
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
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
