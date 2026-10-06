"""JWT emitido por este microservicio (login) y compartido con el resto.

La clave HMAC es JWT_SECRET_KEY. El hash de la contraseña del usuario sigue
en PostgreSQL (bcrypt) y no se usa para firmar.
"""
import bootstrap_shared  # noqa: F401

import config
from libreria_platform.jwt_tokens import (
    TokenError,
    issue_access_token,
    peek_access_token,
    read_access_token,
    signing_key as shared_signing_key,
)


def signing_key():
    return shared_signing_key(config.JWT_PASSWORD)


def issue_token(user):
    token, expires, jti = issue_access_token(
        user,
        config.JWT_MINUTES,
        config.JWT_PASSWORD,
    )
    return token, expires, jti


def read_bearer(header):
    return read_access_token(header, config.JWT_PASSWORD)


def peek_bearer(header):
    return peek_access_token(header, config.JWT_PASSWORD)
