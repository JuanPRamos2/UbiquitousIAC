import os

os.environ["REDIS_URL"] = "memory://"
os.environ["JWT_SECRET_KEY"] = "clave-de-prueba-authors"

from app import app  # noqa: E402
from libreria_platform.jwt_tokens import issue_access_token  # noqa: E402


def _headers(role_id=2):
    token, _expires, _jti = issue_access_token(
        {"id": 2, "email": "ana@example.com", "role": "client" if role_id != 1 else "admin", "role_id": role_id},
        20,
        "no-importa",
    )
    return {"Authorization": "Bearer " + token}


def test_author_writes_are_admin_only():
    client = app.test_client()
    missing = client.post("/authors", json={"nombre": "Nuevo"})
    assert missing.status_code == 401
    denied = client.post("/authors", json={"nombre": "Nuevo"}, headers=_headers(2))
    assert denied.status_code == 403
    removed = client.delete("/authors/1", headers=_headers(2))
    assert removed.status_code == 403
