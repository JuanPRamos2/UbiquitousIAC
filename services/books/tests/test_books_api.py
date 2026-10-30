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
    assert b"<price>" in response.data
    assert b"<publicationYear>" in response.data
    assert b"<coverUrl>" in response.data
    assert b"9780451524935" in response.data
    assert b"1984" in response.data


def test_books_format_json():
    from db.demo_store import reset
    from app import app

    reset()
    client = app.test_client()
    response = client.get("/books?format=json")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["format"] == "json"
    assert payload["count"] >= 30
    isbns = {book["isbn"] for book in payload["books"]}
    assert "9780451524935" in isbns
    assert "9780134444245" in isbns


def test_books_format_json_alias():
    from db.demo_store import reset
    from app import app

    reset()
    client = app.test_client()
    response = client.get("/books?format-json")
    assert response.status_code == 200
    assert response.get_json()["format"] == "json"


def test_books_isbn_json_and_xml():
    from db.demo_store import reset
    from app import app

    reset()
    client = app.test_client()
    xml_response = client.get("/books/9780451524935")
    assert xml_response.status_code == 200
    assert "xml" in xml_response.mimetype
    assert b"1984" in xml_response.data

    json_response = client.get("/books/9780451524935?format=json")
    assert json_response.status_code == 200
    book = json_response.get_json()["book"]
    assert book["isbn"] == "9780451524935"
    assert book["title"] == "1984"
    assert book.get("price") is not None
    assert book.get("publicationYear") is not None
    assert book.get("coverUrl")


def test_accept_header_does_not_override_default_xml():
    from db.demo_store import reset
    from app import app

    reset()
    client = app.test_client()
    response = client.get("/books", headers={"Accept": "application/json"})
    assert "xml" in response.mimetype
    assert response.get_json(silent=True) is None


def test_cloud_concepts_json_and_xml():
    from db.demo_store import reset
    from app import app

    reset()
    client = app.test_client()
    xml_response = client.get("/cloud-concepts")
    assert xml_response.status_code == 200
    assert "xml" in xml_response.mimetype
    assert b"IaaS" in xml_response.data
    assert b"PaaS" in xml_response.data
    assert b"SaaS" in xml_response.data
    assert b"FaaS" in xml_response.data
    assert b"9780134444245" in xml_response.data

    payload = client.get("/cloud-concepts?format=json").get_json()
    names = [model["name"] for model in payload["models"]]
    assert names == ["IaaS", "PaaS", "SaaS", "FaaS"]
    iaas_books = payload["models"][0]["books"]
    assert any(book["isbn"] == "9780134444245" for book in iaas_books)


def test_books_images_json_and_xml():
    from db.demo_store import reset
    from app import app

    reset()
    client = app.test_client()
    xml_response = client.get("/books-images")
    assert xml_response.status_code == 200
    assert "xml" in xml_response.mimetype
    assert b"coverUrl" in xml_response.data
    assert b"9780451524935" in xml_response.data

    payload = client.get("/books-images?format=json").get_json()
    assert payload["count"] >= 30
    orwell = next(book for book in payload["books"] if book["isbn"] == "9780451524935")
    assert orwell["title"] == "1984"
    assert orwell["coverUrl"].endswith("9780451524935.svg")
    assert orwell["images"][0]["isCover"] is True
    assert orwell.get("publicationYear") is not None
    assert orwell.get("price") is not None


def test_cover_image_is_served():
    from app import app

    client = app.test_client()
    response = client.get("/covers/9780451524935.svg")
    assert response.status_code == 200
    mapped = client.get("/covers/cover-9780451524935.png")
    assert mapped.status_code == 200


def _auth_headers(minutes=20, secret=None):
    import uuid
    from datetime import datetime, timedelta, timezone

    import jwt

    from config import settings
    from jwt_auth import signing_key

    now = datetime.now(timezone.utc)
    key = secret or signing_key()
    token = jwt.encode(
        {
            "sub": "1",
            "user_id": 1,
            "email": "admin@example.com",
            "role": "admin",
            "role_id": 1,
            "jti": str(uuid.uuid4()),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=minutes)).timestamp()),
        },
        key,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_books_crud_requires_jwt_from_login():
    from db.demo_store import reset
    from app import app

    reset()
    client = app.test_client()
    headers = _auth_headers()
    denied = client.post("/books?format=json", json={"isbn": "111", "title": "X"})
    assert denied.status_code == 401
    assert denied.get_json()["code"] == "TOKEN_MISSING"
    created = client.post(
        "/books?format=json",
        json={
            "isbn": "9999999999999",
            "title": "Libro nuevo",
            "category": "Prueba",
            "publicationYear": 2024,
            "price": 12.5,
            "authors": ["Ana Ruiz"],
        },
        headers=headers,
    )
    assert created.status_code == 201
    body = created.get_json()
    assert body["ok"] is True
    assert body["book"]["publicationYear"] == 2024
    partial = client.patch(
        "/books/9999999999999?format=json",
        json={"title": "Libro editado"},
        headers=headers,
    )
    assert partial.status_code == 200
    assert partial.get_json()["patched"] == ["title"]
    listed = client.get("/books?format=json").get_json()
    match = next(book for book in listed["books"] if book["isbn"] == "9999999999999")
    assert match["title"] == "Libro editado"
    assert match["publicationYear"] == 2024
    incomplete = client.put(
        "/books/9999999999999?format=json",
        json={"title": "Solo título"},
        headers=headers,
    )
    assert incomplete.status_code == 400
    replaced = client.put(
        "/books/9999999999999?format=json",
        json={
            "title": "Libro reemplazado",
            "authors": ["Ana Ruiz"],
            "category": "Prueba",
            "publicationYear": 2024,
            "price": 12.5,
        },
        headers=headers,
    )
    assert replaced.status_code == 200
    duplicate = client.post(
        "/books?format=json",
        json={"isbn": "9999999999999", "title": "Otra vez"},
        headers=headers,
    )
    assert duplicate.status_code == 409
    missing = client.get("/books/0000000000000?format=json")
    assert missing.status_code == 404
    health = client.get("/health?format=json")
    assert health.status_code in (200, 503)
    assert health.get_json()["service"] == "books"
    deleted = client.delete("/books/9999999999999?format=json", headers=headers)
    assert deleted.status_code == 200
    after = client.get("/books?format=json").get_json()
    assert all(book["isbn"] != "9999999999999" for book in after["books"])
    edited = client.patch(
        "/books/9780134444245?format=json",
        json={"title": "Cloud editado"},
        headers=headers,
    )
    assert edited.status_code == 200
    cloud = client.get("/books/9780134444245?format=json").get_json()["book"]
    assert cloud["title"] == "Cloud editado"
    assert any(concept["name"] == "IaaS" for concept in cloud["concepts"])
    hidden = client.delete("/books/9780451524935?format=json", headers=headers)
    assert hidden.status_code == 200
    after_hide = client.get("/books?format=json").get_json()
    assert all(book["isbn"] != "9780451524935" for book in after_hide["books"])


def test_books_rejects_bad_tokens_and_keeps_get_public():
    from db.demo_store import reset
    from app import app

    reset()
    client = app.test_client()
    public = client.get("/books/9780451524935?format=json")
    assert public.status_code == 200
    expired = client.post(
        "/books?format=json",
        json={"isbn": "111", "title": "X"},
        headers=_auth_headers(minutes=-5),
    )
    assert expired.status_code == 401
    assert expired.get_json()["code"] == "TOKEN_EXPIRED"
    foreign = client.post(
        "/books?format=json",
        json={"isbn": "111", "title": "X"},
        headers=_auth_headers(secret="otra-clave-que-no-coincide-con-el-login"),
    )
    assert foreign.status_code == 401
    assert foreign.get_json()["code"] == "TOKEN_INVALID"
    malformed = client.delete(
        "/books/9780451524935?format=json",
        headers={"Authorization": "Token abc"},
    )
    assert malformed.status_code == 401
    assert malformed.get_json()["code"] == "TOKEN_MALFORMED"


def test_practice_shim_app_services_soap_loads():
    import importlib.util
    from pathlib import Path

    shim = Path(__file__).resolve().parents[3] / "app" / "services" / "soap" / "app.py"
    assert shim.is_file()
    spec = importlib.util.spec_from_file_location("practice_soap_app", shim)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    client = module.app.test_client()
    response = client.get("/books")
    assert response.status_code == 200
    assert b"<price>" in response.data
    assert b"<coverUrl>" in response.data
