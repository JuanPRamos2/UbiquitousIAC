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


def test_books_crud_requires_admin():
    from db.demo_store import reset
    from app import app

    reset()
    client = app.test_client()
    denied = client.post("/books?format=json", json={"isbn": "111", "title": "X"})
    assert denied.status_code == 403
    created = client.post(
        "/books?format=json",
        json={"isbn": "9999999999999", "title": "Libro nuevo", "category": "Prueba"},
        headers={"X-User-Role": "admin"},
    )
    assert created.status_code == 201
    assert created.get_json()["ok"] is True
    deleted = client.delete(
        "/books/9999999999999?format=json", headers={"X-User-Role": "admin"}
    )
    assert deleted.status_code == 200


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
