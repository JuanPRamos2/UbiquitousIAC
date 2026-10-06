import os

os.environ["REDIS_URL"] = "memory://"
os.environ["JWT_SECRET_KEY"] = "clave-de-prueba"

from libreria_platform.jwt_tokens import (  # noqa: E402
    TokenError,
    issue_access_token,
    read_access_token,
    revoke,
)
from libreria_platform.redis_store import MemoryBackend, store  # noqa: E402


def test_session_roundtrip_and_revocation():
    store._client = MemoryBackend()
    store._url = "memory://"
    token, expires, jti = issue_access_token(
        {"id": 4, "email": "ana@example.com", "role": "client", "role_id": 2},
        20,
        "no-se-usa-si-hay-secret",
    )
    claims = read_access_token("Bearer " + token, "no-se-usa-si-hay-secret")
    assert claims["user_id"] == 4
    assert claims["role_id"] == 2
    assert claims["jti"] == jti
    store.setex("session:" + jti, 60, "1")
    store.setex("refresh:abc", 60, "1")
    assert store.get("session:" + jti) == "1"
    revoke(jti, int(expires.timestamp()))
    store.delete("session:" + jti, "refresh:abc")
    assert store.get("session:" + jti) is None
    try:
        read_access_token("Bearer " + token, "no-se-usa")
    except TokenError as exc:
        assert exc.code == "TOKEN_REVOKED"
    else:
        raise AssertionError("el token revocado fue aceptado")


def test_cache_is_optional_when_redis_url_is_missing(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    fresh = store.__class__()
    assert fresh.get("books:list:all", optional=True) is None
    saved = fresh.setex("books:1", 10, "{}", optional=True)
    assert saved is False or saved is None


def test_missing_bearer():
    try:
        read_access_token("", "x")
    except TokenError as exc:
        assert exc.code == "TOKEN_MISSING"
    else:
        raise AssertionError("aceptó un encabezado vacío")
