"""Lectura de books / book_concepts / imágenes del monolito EG02 (sólo SELECT)."""
from collections import defaultdict

from db.connection import fetch_all
import library_catalog


def _row(item):
    if item is None:
        return {}
    return dict(item)


def list_books():
    rows = fetch_all(
        """
        SELECT b.isbn, b.title, b.description, b.publication_year AS publication_year,
               b.price, b.stock, cat.name AS category, f.name AS format
        FROM books b
        JOIN categories cat ON cat.id = b.category_id
        LEFT JOIN formats f ON f.id = b.format_id
        ORDER BY b.title
        """
    )
    authors = fetch_all(
        """
        SELECT b.isbn, a.full_name
        FROM book_authors ba
        JOIN books b ON b.id = ba.book_id
        JOIN authors a ON a.id = ba.author_id
        ORDER BY a.full_name
        """
    )
    concepts = fetch_all(
        """
        SELECT b.isbn, c.id AS concept_id, c.name, bc.definition, bc.chapter, bc.page_number
        FROM book_concepts bc
        JOIN books b ON b.id = bc.book_id
        JOIN concepts c ON c.id = bc.concept_id
        ORDER BY c.name
        """
    )
    by_isbn = {}
    for raw in rows:
        row = _row(raw)
        isbn = row["isbn"]
        by_isbn[isbn] = {
            "isbn": isbn,
            "title": row["title"],
            "publicationYear": row.get("publication_year"),
            "price": float(row["price"]) if row.get("price") is not None else None,
            "stock": row.get("stock"),
            "format": row.get("format") or "",
            "category": row.get("category") or "",
            "description": row.get("description") or "",
            "authors": [],
            "coverUrl": library_catalog.cover_path(isbn),
            "concepts": [],
        }
    for raw in authors:
        row = _row(raw)
        book = by_isbn.get(row["isbn"])
        if book:
            book["authors"].append(row["full_name"])
    for raw in concepts:
        row = _row(raw)
        book = by_isbn.get(row["isbn"])
        if book:
            book["concepts"].append(
                {
                    "conceptId": row["concept_id"],
                    "name": row["name"],
                    "definition": row.get("definition") or "",
                    "chapter": row.get("chapter") or "",
                    "pageNumber": row.get("page_number"),
                }
            )
    return list(by_isbn.values())


def list_cloud_concepts():
    rows = fetch_all(
        """
        SELECT c.name AS model_name, c.description AS model_description,
               b.isbn, b.title, b.description AS book_description,
               cat.name AS category, bc.definition, bc.chapter, bc.page_number
        FROM concepts c
        JOIN book_concepts bc ON bc.concept_id = c.id
        JOIN books b ON b.id = bc.book_id
        JOIN categories cat ON cat.id = b.category_id
        WHERE c.name IN ('IaaS', 'PaaS', 'SaaS', 'FaaS')
        ORDER BY c.name, b.title
        """
    )
    authors = fetch_all(
        """
        SELECT b.isbn, a.full_name
        FROM book_authors ba
        JOIN books b ON b.id = ba.book_id
        JOIN authors a ON a.id = ba.author_id
        ORDER BY a.full_name
        """
    )
    authors_by_isbn = defaultdict(list)
    for raw in authors:
        row = _row(raw)
        authors_by_isbn[row["isbn"]].append(row["full_name"])

    grouped = {
        model["name"]: {**model, "books": []}
        for model in library_catalog.CLOUD_MODELS
    }
    for raw in rows:
        row = _row(raw)
        name = row["model_name"]
        if name not in grouped:
            continue
        isbn = row["isbn"]
        grouped[name]["description"] = row.get("model_description") or grouped[name]["description"]
        grouped[name]["books"].append(
            {
                "isbn": isbn,
                "title": row["title"],
                "category": row.get("category") or "",
                "authors": authors_by_isbn.get(isbn, []),
                "description": row.get("book_description") or "",
                "definition": row.get("definition") or "",
                "chapter": row.get("chapter") or "",
                "pageNumber": row.get("page_number"),
                "coverUrl": library_catalog.cover_path(isbn),
            }
        )
    return [grouped[model["name"]] for model in library_catalog.CLOUD_MODELS]


def list_books_images():
    rows = fetch_all(
        """
        SELECT b.isbn, b.title, cat.name AS category,
               i.stored_name, i.alt_text, i.mime_type, bi.is_cover
        FROM books b
        JOIN categories cat ON cat.id = b.category_id
        LEFT JOIN book_images bi ON bi.book_id = b.id
        LEFT JOIN images i ON i.id = bi.image_id
        ORDER BY b.title, bi.is_cover DESC
        """
    )
    authors = fetch_all(
        """
        SELECT b.isbn, a.full_name
        FROM book_authors ba
        JOIN books b ON b.id = ba.book_id
        JOIN authors a ON a.id = ba.author_id
        ORDER BY a.full_name
        """
    )
    authors_by_isbn = defaultdict(list)
    for raw in authors:
        row = _row(raw)
        authors_by_isbn[row["isbn"]].append(row["full_name"])

    by_isbn = {}
    for raw in rows:
        row = _row(raw)
        isbn = row["isbn"]
        if isbn not in by_isbn:
            by_isbn[isbn] = {
                "isbn": isbn,
                "title": row["title"],
                "authors": authors_by_isbn.get(isbn, []),
                "category": row.get("category") or "",
                "coverUrl": library_catalog.cover_path(isbn),
                "images": [],
            }
        if row.get("stored_name"):
            by_isbn[isbn]["images"].append(
                {
                    "url": library_catalog.cover_path(isbn),
                    "storedName": row["stored_name"],
                    "alt": row.get("alt_text") or f"Portada de {row['title']}",
                    "mimeType": "image/svg+xml",
                    "isCover": bool(row.get("is_cover")),
                }
            )
        elif not by_isbn[isbn]["images"]:
            by_isbn[isbn]["images"].append(
                {
                    "url": library_catalog.cover_path(isbn),
                    "storedName": library_catalog.stored_cover_name(isbn),
                    "alt": f"Portada de {row['title']}",
                    "mimeType": "image/svg+xml",
                    "isCover": True,
                }
            )
    return list(by_isbn.values())
