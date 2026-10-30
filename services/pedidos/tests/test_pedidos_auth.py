import os

os.environ["REDIS_URL"] = "memory://"
os.environ["JWT_SECRET_KEY"] = "clave-de-prueba-pedidos"

from app import app  # noqa: E402


def test_orders_are_not_public():
    client = app.test_client()
    listed = client.get("/pedidos")
    assert listed.status_code == 401
    assert listed.get_json()["code"] == "TOKEN_MISSING"
    created = client.post("/pedidos", json={"lines": [{"isbn": "9780451524935", "quantity": 1}]})
    assert created.status_code == 401
    removed = client.delete("/pedidos/1")
    assert removed.status_code == 401
