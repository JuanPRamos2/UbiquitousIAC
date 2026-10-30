import os

os.environ["REDIS_URL"] = "memory://"
os.environ["JWT_SECRET_KEY"] = "clave-de-prueba-pagos"

from app import app  # noqa: E402
from libreria_platform.jwt_tokens import issue_access_token  # noqa: E402


def _headers(role_id):
    role = "admin" if role_id == 1 else "client"
    token, _expires, _jti = issue_access_token(
        {"id": 4, "email": "ana@example.com", "role": role, "role_id": role_id},
        20,
        "no-importa",
    )
    return {"Authorization": "Bearer " + token}


def test_payments_require_jwt_and_admin_to_delete():
    client = app.test_client()
    missing = client.post("/pagos", json={"order_id": 1, "amount": 10, "method": "efectivo"})
    assert missing.status_code == 401
    denied = client.delete("/pagos/1", headers=_headers(2))
    assert denied.status_code == 403
    listed = client.get("/pagos")
    assert listed.status_code == 401
