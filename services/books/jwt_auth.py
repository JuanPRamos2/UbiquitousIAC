"""Verifica el JWT que emite el microservicio de login.

Este servicio no crea tokens. JWT_SECRET_KEY tiene que coincidir con el login.
Antes de aceptar el token consulta jwt:revoked:<jti> en Redis.
"""
import bootstrap_shared  # noqa: F401

from config import settings
from libreria_platform.jwt_tokens import (
    TokenError,
    read_access_token,
    signing_key as shared_signing_key,
)


def signing_key():
    return shared_signing_key(settings.JWT_PASSWORD)


def read_bearer(header):
    return read_access_token(header, settings.JWT_PASSWORD)
