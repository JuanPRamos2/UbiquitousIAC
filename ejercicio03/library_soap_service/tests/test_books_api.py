def test_books_default_is_xml():
    from db.demo_store import reset
    from app import app

    reset()
    client = app.test_client()
    response = client.get("/books")
    assert response.status_code == 200
    assert "xml" in response.mimetype
    assert b"<books>" in response.data
    assert b"<isbn>" in response.data


def test_books_format_json():
    from db.demo_store import reset
    from app import app

    reset()
    client = app.test_client()
    response = client.get("/books?format=json")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["format"] == "json"
    assert payload["count"] >= 1
    assert "isbn" in payload["books"][0]


def test_books_format_json_alias():
    from db.demo_store import reset
    from app import app

    reset()
    client = app.test_client()
    response = client.get("/books?format-json")
    assert response.status_code == 200
    assert response.get_json()["format"] == "json"


def test_books_crud_requires_admin():
    from db.demo_store import reset
    from app import app

    reset()
    client = app.test_client()
    denied = client.post("/books", json={"isbn": "111", "title": "X"})
    assert denied.status_code == 403
    created = client.post(
        "/books",
        json={"isbn": "9999999999999", "title": "Libro nuevo", "category": "Prueba"},
        headers={"X-User-Role": "admin"},
    )
    assert created.status_code == 201
    deleted = client.delete("/books/9999999999999", headers={"X-User-Role": "admin"})
    assert deleted.status_code == 200
