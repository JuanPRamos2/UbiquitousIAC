"""Catálogo bilingüe XML/JSON del microservicio Flask.

GET /books
GET /books/<isbn>
GET /cloud-concepts
GET /books-images

Sin ?format= el servicio responde XML. Con ?format=json responde JSON.
Las lecturas GET se pueden cachear en Redis. Si Redis no responde, se lee
el catálogo igual. Las escrituras exigen JWT de administrador y, si Redis
no puede confirmar la revocación, se rechazan.
"""
import json
from xml.etree import ElementTree as ET

from flask import Response, request

import bootstrap_shared  # noqa: F401
from config import settings
from db import catalog as catalog_store
from db import demo_store
from jwt_auth import TokenError, read_bearer
from libreria_platform.jwt_tokens import is_admin
from libreria_platform.redis_store import store
from xml_format import respond, wants_json


def _stamp(result, cache):
    response = result[0] if isinstance(result, tuple) else result
    response.headers["X-Cache"] = cache
    return result


def _require_jwt():
    """POST, PUT, PATCH y DELETE exigen un JWT de administrador.

    GET /books y GET /books/<isbn> siguen públicos.
    """
    try:
        claims = read_bearer(request.headers.get("Authorization"))
    except TokenError as exc:
        status = 503 if exc.code == "REDIS_UNAVAILABLE" else 401
        return None, respond(
            {
                "ok": False,
                "code": exc.code,
                "error": exc.message,
                "errors": [exc.message],
            },
            root_tag="error",
            status=status,
        )
    if not is_admin(claims):
        return None, respond(
            {
                "ok": False,
                "code": "FORBIDDEN",
                "error": "Rol insuficiente para modificar el catálogo.",
                "errors": ["Rol insuficiente para modificar el catálogo."],
            },
            root_tag="error",
            status=403,
        )
    return claims, None


def _list_key():
    parts = []
    for key in sorted(request.args):
        if key in ("format", "format-json"):
            continue
        parts.append(f"{key}={request.args.get(key)}")
    return "books:list:" + ("|".join(parts) if parts else "all")


def _remember(key, payload):
    store.setex(
        key,
        settings.BOOKS_CACHE_TTL,
        json.dumps(payload, default=str),
        optional=True,
    )


def _cached_list():
    key = _list_key()
    raw = store.get(key, optional=True)
    if raw:
        store.mark_hit()
        try:
            return json.loads(raw), "HIT"
        except json.JSONDecodeError:
            pass
    books = catalog_store.list_books()
    store.mark_miss()
    _remember(key, books)
    state = "MISS" if store.ping() else "BYPASS"
    return books, state


def _cached_book(isbn):
    key = f"books:{isbn}"
    raw = store.get(key, optional=True)
    if raw:
        store.mark_hit()
        try:
            return json.loads(raw), "HIT"
        except json.JSONDecodeError:
            pass
    book = catalog_store.get_book(isbn)
    if book:
        store.mark_miss()
        _remember(key, book)
        state = "MISS" if store.ping() else "BYPASS"
        return book, state
    return None, "MISS"


def _invalidate_catalog():
    store.delete_pattern("books:*", optional=True)


def books_xml(books):
    root = ET.Element("books")
    ET.SubElement(root, "count").text = str(len(books))
    for book in books:
        node = ET.SubElement(root, "book")
        ET.SubElement(node, "isbn").text = book.get("isbn") or ""
        ET.SubElement(node, "title").text = book.get("title") or ""
        ET.SubElement(node, "category").text = book.get("category") or ""
        if book.get("description"):
            ET.SubElement(node, "description").text = book["description"]
        if book.get("publicationYear") is not None:
            ET.SubElement(node, "publicationYear").text = str(book["publicationYear"])
        if book.get("price") is not None:
            ET.SubElement(node, "price").text = f"{float(book['price']):.2f}"
        if book.get("coverUrl"):
            ET.SubElement(node, "coverUrl").text = book["coverUrl"]
        authors = ET.SubElement(node, "authors")
        for author in book.get("authors") or []:
            ET.SubElement(authors, "author").text = author
        concepts = ET.SubElement(node, "concepts")
        for concept in book.get("concepts") or []:
            c = ET.SubElement(concepts, "concept")
            ET.SubElement(c, "conceptId").text = str(concept.get("conceptId", ""))
            ET.SubElement(c, "name").text = concept.get("name") or ""
            ET.SubElement(c, "definition").text = concept.get("definition") or ""
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def register_books_routes(app):
    @app.get("/books")
    def list_books():
        books, cache = _cached_list()
        if wants_json():
            return _stamp(respond({"format": "json", "count": len(books), "books": books}), cache)
        return _stamp(Response(books_xml(books), mimetype="application/xml; charset=utf-8"), cache)

    @app.get("/books/<isbn>")
    def get_book(isbn):
        book, cache = _cached_book(isbn)
        if not book:
            return respond(
                {"error": "Libro no encontrado", "isbn": isbn},
                root_tag="error",
                status=404,
            )
        if wants_json():
            return _stamp(respond({"format": "json", "book": book}), cache)
        return _stamp(Response(books_xml([book]), mimetype="application/xml; charset=utf-8"), cache)

    @app.get("/cloud-concepts")
    def cloud_concepts():
        models = catalog_store.list_cloud_concepts()
        return respond(
            {
                "format": "json" if wants_json() else "xml",
                "count": len(models),
                "models": models,
            },
            root_tag="cloudConcepts",
        )

    @app.get("/books-images")
    def books_images():
        books = catalog_store.list_books_images()
        return respond(
            {
                "format": "json" if wants_json() else "xml",
                "count": len(books),
                "books": books,
            },
            root_tag="booksImages",
        )

    @app.post("/books")
    def create_book():
        _claims, denied = _require_jwt()
        if denied:
            return denied
        payload = request.get_json(silent=True) or {}
        try:
            book = demo_store.upsert_book(payload, create=True)
        except ValueError as exc:
            text = str(exc)
            status = 409 if "ya existe" in text.lower() else 400
            return respond({"error": text}, root_tag="error", status=status)
        _invalidate_catalog()
        return respond({"ok": True, "book": book}, root_tag="result", status=201)

    @app.put("/books/<isbn>")
    def update_book(isbn):
        _claims, denied = _require_jwt()
        if denied:
            return denied
        payload = request.get_json(silent=True) or {}
        payload["isbn"] = isbn
        missing = [
            name
            for name in ("title", "authors", "category", "publicationYear", "price")
            if name not in payload or payload.get(name) in (None, "", [])
        ]
        if missing:
            return respond(
                {
                    "error": (
                        "PUT reemplaza el libro completo. Faltan: "
                        + ", ".join(missing)
                        + ". Use PATCH para cambiar solo un dato."
                    )
                },
                root_tag="error",
                status=400,
            )
        try:
            book = demo_store.upsert_book(payload, create=False)
        except ValueError as exc:
            return respond({"error": str(exc)}, root_tag="error", status=400)
        if book is None:
            return respond({"error": "Libro no encontrado"}, root_tag="error", status=404)
        _invalidate_catalog()
        return respond({"ok": True, "book": book}, root_tag="result")

    @app.delete("/books/<isbn>")
    def delete_book(isbn):
        _claims, denied = _require_jwt()
        if denied:
            return denied
        deleted = demo_store.delete_book(isbn)
        if not deleted:
            return respond({"error": "Libro no encontrado"}, root_tag="error", status=404)
        _invalidate_catalog()
        return respond({"ok": True, "isbn": isbn}, root_tag="result")

    @app.patch("/books/<isbn>")
    def patch_book(isbn):
        _claims, denied = _require_jwt()
        if denied:
            return denied
        payload = request.get_json(silent=True) or {}
        changes = {key: value for key, value in payload.items() if key != "isbn"}
        if not changes:
            return respond(
                {"error": "PATCH necesita al menos un campo para modificar."},
                root_tag="error",
                status=400,
            )
        current = catalog_store.get_book(isbn)
        if not current:
            return respond({"error": "Libro no encontrado", "isbn": isbn}, root_tag="error", status=404)
        merged = {"isbn": isbn, "title": current.get("title") or ""}
        merged.update(changes)
        try:
            book = demo_store.upsert_book(merged, create=False)
        except ValueError as exc:
            return respond({"error": str(exc)}, root_tag="error", status=400)
        if book is None:
            return respond({"error": "Libro no encontrado", "isbn": isbn}, root_tag="error", status=404)
        _invalidate_catalog()
        return respond({"ok": True, "book": book, "patched": list(changes)}, root_tag="result")

    @app.get("/health")
    def books_health():
        if settings.SOAP_DEMO:
            redis_ok = store.ping()
            return respond(
                {
                    "status": "ok" if redis_ok else "degraded",
                    "service": "books",
                    "database": "ok",
                    "redis": "ok" if redis_ok else "error",
                    "mode": "demo",
                },
                root_tag="health",
            )
        try:
            from db.connection import fetch_one

            fetch_one("SELECT 1 AS ok")
        except Exception:
            return respond(
                {
                    "status": "degraded",
                    "service": "books",
                    "database": "error",
                    "mode": "postgres",
                    "error": "El servicio responde, pero la base de datos no está disponible.",
                },
                root_tag="health",
                status=503,
            )
        redis_ok = store.ping()
        return respond(
            {
                "status": "ok" if redis_ok else "degraded",
                "service": "books",
                "database": "ok",
                "redis": "ok" if redis_ok else "error",
                "mode": "postgres",
            },
            root_tag="health",
            status=200,
        )

    @app.get("/metrics")
    def books_metrics():
        snap = store.snapshot()
        return respond(
            {"service": "books", "redis": snap},
            root_tag="metrics",
            status=200 if snap.get("connected") else 503,
        )
