"""Catálogo de libros del microservicio.

GET /books            XML por defecto
GET /books?format=json  JSON
GET /books?format-json  JSON (alias)
"""
from xml.etree import ElementTree as ET

from flask import Response, jsonify, request

from db import demo_store


def wants_json():
    fmt = (request.args.get("format") or "").strip().lower()
    if fmt in ("json", "application/json"):
        return True
    if "format-json" in request.args:
        return True
    accept = (request.headers.get("Accept") or "").lower()
    return "application/json" in accept and "xml" not in accept


def _unique_books():
    seen = {}
    for item in demo_store.CATALOGO:
        isbn = item["isbn"]
        if isbn not in seen:
            seen[isbn] = {
                "isbn": isbn,
                "title": item["book_title"],
                "category": item["category_name"],
                "concepts": [],
            }
        seen[isbn]["concepts"].append(
            {
                "conceptId": item["concept_id"],
                "name": item["concept_name"],
                "definition": item["definition"],
            }
        )
    extra = demo_store.list_extra_books()
    for book in extra:
        seen[book["isbn"]] = book
    return list(seen.values())


def books_xml(books):
    ET.register_namespace("", "")
    root = ET.Element("books")
    for book in books:
        node = ET.SubElement(root, "book")
        ET.SubElement(node, "isbn").text = book["isbn"]
        ET.SubElement(node, "title").text = book["title"]
        ET.SubElement(node, "category").text = book.get("category") or ""
        concepts = ET.SubElement(node, "concepts")
        for concept in book.get("concepts") or []:
            c = ET.SubElement(concepts, "concept")
            ET.SubElement(c, "conceptId").text = str(concept.get("conceptId", ""))
            ET.SubElement(c, "name").text = concept.get("name") or ""
            ET.SubElement(c, "definition").text = concept.get("definition") or ""
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _require_admin():
    role = (request.headers.get("X-User-Role") or request.args.get("role") or "").lower()
    return role == "admin"


def register_books_routes(app):
    @app.get("/books")
    def list_books():
        books = _unique_books()
        if wants_json():
            return jsonify({"format": "json", "count": len(books), "books": books})
        return Response(books_xml(books), mimetype="application/xml; charset=utf-8")

    @app.get("/books/<isbn>")
    def get_book(isbn):
        books = [book for book in _unique_books() if book["isbn"] == isbn]
        if not books:
            if wants_json():
                return jsonify({"error": "Libro no encontrado", "isbn": isbn}), 404
            return Response(
                b'<?xml version="1.0"?><error>Libro no encontrado</error>',
                status=404,
                mimetype="application/xml; charset=utf-8",
            )
        book = books[0]
        if wants_json():
            return jsonify({"format": "json", "book": book})
        return Response(books_xml([book]), mimetype="application/xml; charset=utf-8")

    @app.post("/books")
    def create_book():
        if not _require_admin():
            return jsonify({"error": "Se requiere usuario admin"}), 403
        payload = request.get_json(silent=True) or {}
        try:
            book = demo_store.upsert_book(payload, create=True)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True, "book": book}), 201

    @app.put("/books/<isbn>")
    def update_book(isbn):
        if not _require_admin():
            return jsonify({"error": "Se requiere usuario admin"}), 403
        payload = request.get_json(silent=True) or {}
        payload["isbn"] = isbn
        book = demo_store.upsert_book(payload, create=False)
        if book is None:
            return jsonify({"error": "Libro no encontrado"}), 404
        return jsonify({"ok": True, "book": book})

    @app.delete("/books/<isbn>")
    def delete_book(isbn):
        if not _require_admin():
            return jsonify({"error": "Se requiere usuario admin"}), 403
        deleted = demo_store.delete_book(isbn)
        if not deleted:
            return jsonify({"error": "Libro no encontrado"}), 404
        return jsonify({"ok": True, "isbn": isbn})
