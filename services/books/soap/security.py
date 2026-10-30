import hashlib
import hmac
import logging
import os

from config import settings
from soap.envelope import find_child, local_name, text_of
from soap.faults import unauthorized_fault

logger = logging.getLogger(__name__)


def hash_password(password, iterations=260000, salt=None):
    if salt is None:
        salt = os.urandom(16)
    elif isinstance(salt, str):
        salt = bytes.fromhex(salt)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password, stored_hash):
    if not password or not stored_hash:
        return False
    try:
        algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        int(iterations),
    )
    return hmac.compare_digest(candidate.hex(), digest_hex)


def _find_security(header):
    if header is None:
        return None
    for child in list(header):
        if local_name(child.tag) == "Security":
            return child
    return None


def _find_username_token(security):
    if security is None:
        return None
    token = find_child(security, "UsernameToken")
    if token is not None:
        return token
    for child in list(security):
        if local_name(child.tag) == "UsernameToken":
            return child
    return None


def require_username_token(header):
    security = _find_security(header)
    token = _find_username_token(security)
    if token is None:
        logger.warning("Llamada a operación protegida sin UsernameToken")
        raise unauthorized_fault()

    username = text_of(token, "Username")
    password = text_of(token, "Password")
    expected_user = settings.SOAP_STATS_USERNAME
    expected_hash = settings.SOAP_STATS_PASSWORD_HASH

    if username != expected_user or not verify_password(password, expected_hash):
        logger.warning("WS-Security rechazado para usuario=%s", username)
        raise unauthorized_fault()
    return username
