import health_api
from books_api import filter_books
from config_store import load, restore_defaults, save
from http_api import HttpClient, authorization_value, format_exchange, mask_secrets


def test_filter_by_isbn_title_year_and_price():
    books = [
        {"isbn": "111", "title": "Dune", "publicationYear": 1965, "price": 20},
        {"isbn": "222", "title": "1984", "publicationYear": 1949, "price": 10},
        {"isbn": "333", "title": "Fundación", "publicationYear": 1951, "price": 30},
    ]
    assert [book["isbn"] for book in filter_books(books, title="dun")] == ["111"]
    assert [book["isbn"] for book in filter_books(books, year="1949")] == ["222"]
    assert [book["isbn"] for book in filter_books(books, price_min="15", price_max="25")] == ["111"]
    assert [book["isbn"] for book in filter_books(books, isbn="33")] == ["333"]


def test_health_three_states():
    assert health_api.classify(0, {}) == "down"
    assert health_api.classify(200, {"database": "ok"}) == "up"
    assert health_api.classify(200, {"postgres": "ok"}) == "up"
    assert health_api.classify(503, {"postgres": "error"}) == "degraded"
    assert health_api.classify(200, {"database": "error"}) == "degraded"
    assert health_api.classify(404, {}) == "degraded"


def test_console_log_masks_password_and_shows_bearer():
    masked = mask_secrets({"email": "ana@example.com", "password": "ClaveSegura26"})
    assert masked["password"] == "***"
    assert masked["email"] == "ana@example.com"
    assert authorization_value("", True) is None
    assert authorization_value("abc.def.ghi", False) is None
    assert authorization_value("abc.def.ghi", True) == "Bearer abc.def.ghi"
    text = format_exchange(
        "POST",
        "http://localhost:5000/login?format=json",
        {"Accept": "application/json", "Content-Type": "application/json"},
        {"email": "ana@example.com", "password": "ClaveSegura26"},
        401,
        {"code": "CREDENTIALS_INVALID", "errors": ["Credenciales incorrectas."]},
        "Esta operación es pública: no se envía Authorization.",
    )
    assert "POST" in text
    assert "Bearer" not in text
    assert "ClaveSegura26" not in text
    assert "Credenciales incorrectas." in text
    assert "***" in text


def test_token_is_stored_for_later_requests(monkeypatch, tmp_path):
    monkeypatch.setenv("LIBRERIA_PYTHON_HOME", str(tmp_path))
    client = HttpClient("http://localhost:5000", "http://localhost:5001")
    client.set_token("aaa.bbb.ccc")
    restored = HttpClient("http://localhost:5000", "http://localhost:5001")
    assert restored.token == "aaa.bbb.ccc"
    assert authorization_value(restored.token, True).startswith("Bearer ")
    restored.clear_token()
    empty = HttpClient("http://localhost:5000", "http://localhost:5001")
    assert empty.token == ""


def test_config_persists_and_restores(monkeypatch, tmp_path):
    monkeypatch.setenv("LIBRERIA_PYTHON_HOME", str(tmp_path))
    monkeypatch.delenv("LIBRERIA_LOGIN_URL", raising=False)
    monkeypatch.delenv("LIBRERIA_BOOKS_URL", raising=False)
    saved = save("http://10.0.0.8:5000/", "http://10.0.0.8:5001/")
    assert saved["loginUrl"] == "http://10.0.0.8:5000"
    assert load()["booksUrl"] == "http://10.0.0.8:5001"
    restored = restore_defaults()
    assert restored["loginUrl"] == "http://localhost:5000"
    assert load()["booksUrl"] == "http://localhost:5001"
