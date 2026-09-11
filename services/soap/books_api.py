"""Catálogo bilingüe XML/JSON del microservicio Flask.

GET /books
GET /books/<isbn>
GET /cloud-concepts
GET /books-images

Sin ?format= el servicio responde XML. Con ?format=json responde JSON.
"""
from xml.etree import ElementTree as ET

from flask import Response, request

from db import catalog as catalog_store
from db import demo_store
from xml_format import respond, wants_json


def _require_admin():
    role = (request.headers.get("X-User-Role") or request.args.get("role") or "").lower()
    return role == "admin"


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
        if not _require_admin():
            return respond({"error": "Se requiere usuario admin"}, root_tag="error", status=403)
        payload = request.get_json(silent=True) or {}
        try:
            book = demo_store.upsert_book(payload, create=True)
        except ValueError as exc:
            return respond({"error": str(exc)}, root_tag="error", status=400)
        return respond({"ok": True, "book": book}, root_tag="result", status=201)

    @app.put("/books/<isbn>")
    def update_book(isbn):
        if not _require_admin():
            return respond({"error": "Se requiere usuario admin"}, root_tag="error", status=403)
        payload = request.get_json(silent=True) or {}
        payload["isbn"] = isbn
        book = demo_store.upsert_book(payload, create=False)
        if book is None:
            return respond({"error": "Libro no encontrado"}, root_tag="error", status=404)
        return respond({"ok": True, "book": book}, root_tag="result")

    @app.delete("/books/<isbn>")
    def delete_book(isbn):
        if not _require_admin():
            return respond({"error": "Se requiere usuario admin"}, root_tag="error", status=403)
        deleted = demo_store.delete_book(isbn)
        if not deleted:
            return respond({"error": "Libro no encontrado"}, root_tag="error", status=404)
        return respond({"ok": True, "isbn": isbn}, root_tag="result")
