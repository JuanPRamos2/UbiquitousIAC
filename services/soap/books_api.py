"""Catálogo bilingüe XML/JSON del microservicio Flask.

GET /books
GET /books/<isbn>
GET /cloud-concepts
GET /books-images

Sin ?format= el servicio responde XML. Con ?format=json responde JSON.
"""
from xml.etree import ElementTree as ET

from flask import Response, request

from config import settings
from db import catalog as catalog_store
from db import demo_store
from jwt_auth import TokenError, read_bearer
from xml_format import respond, wants_json


def _require_jwt():
    """POST, PUT, PATCH y DELETE exigen un JWT emitido por el login.

    GET /books y GET /books/<isbn> siguen públicos.
    """
    try:
        return read_bearer(request.headers.get("Authorization")), None
    except TokenError as exc:
        return None, respond(
            {
                "ok": False,
                "code": exc.code,
                "error": exc.message,
                "errors": [exc.message],
            },
            root_tag="error",
            status=401,
        )


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
        books = catalog_store.list_books()
        if wants_json():
            return respond({"format": "json", "count": len(books), "books": books})
        return Response(books_xml(books), mimetype="application/xml; charset=utf-8")

    @app.get("/books/<isbn>")
    def get_book(isbn):
        book = catalog_store.get_book(isbn)
        if not book:
            return respond(
                {"error": "Libro no encontrado", "isbn": isbn},
                root_tag="error",
                status=404,
            )
        if wants_json():
            return respond({"format": "json", "book": book})
        return Response(books_xml([book]), mimetype="application/xml; charset=utf-8")

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
        return respond({"ok": True, "book": book}, root_tag="result")

    @app.delete("/books/<isbn>")
    def delete_book(isbn):
        _claims, denied = _require_jwt()
        if denied:
            return denied
        deleted = demo_store.delete_book(isbn)
        if not deleted:
            return respond({"error": "Libro no encontrado"}, root_tag="error", status=404)
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
        return respond({"ok": True, "book": book, "patched": list(changes)}, root_tag="result")

    @app.get("/health")
    def books_health():
        if settings.SOAP_DEMO:
            return respond(
                {
                    "status": "ok",
                    "service": "books",
                    "database": "ok",
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
        return respond(
            {
                "status": "ok",
                "service": "books",
                "database": "ok",
                "mode": "postgres",
            },
            root_tag="health",
        )
