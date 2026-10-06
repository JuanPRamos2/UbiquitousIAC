import os

os.environ["REDIS_URL"] = "memory://"
os.environ["JWT_SECRET_KEY"] = "clave-de-prueba-users"

from app import app  # noqa: E402
from libreria_platform.jwt_tokens import issue_access_token  # noqa: E402


def _headers(role_id, role, user_id=2):
    token, _expires, _jti = issue_access_token(
        {"id": user_id, "email": "ana@example.com", "role": role, "role_id": role_id},
        20,
        "no-importa",
    )
    return {"Authorization": "Bearer " + token}


def test_writes_require_admin_jwt():
    client = app.test_client()
    missing = client.post("/users", json={"nombre": "Ana"})
    assert missing.status_code == 401
    assert missing.get_json()["code"] == "TOKEN_MISSING"
    denied = client.get("/users", headers=_headers(2, "client"))
    assert denied.status_code == 403
    assert denied.get_json()["code"] == "FORBIDDEN"
    created = client.delete("/users/3", headers=_headers(2, "client"))
    assert created.status_code == 403


def test_password_needs_the_owner_and_three_values():
    client = app.test_client()
    foreign = client.post(
        "/users/2/password",
        json={
            "currentPassword": "ClaveActual26",
            "newPassword": "ClaveNueva26",
            "confirmPassword": "ClaveNueva26",
        },
        headers=_headers(2, "client", user_id=9),
    )
    assert foreign.status_code == 403
    incomplete = client.post(
        "/users/2/password",
        json={"currentPassword": "ClaveActual26", "newPassword": "ClaveNueva26"},
        headers=_headers(2, "client", user_id=2),
    )
    assert incomplete.status_code == 400
    assert "tres contraseñas" in incomplete.get_json()["error"]
