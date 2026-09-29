"""Catálogo de demostración para el módulo SOAP cuando no hay PostgreSQL.

Usa los mismos libros y conceptos del Ejercicio guiado 02 (IaaS, PaaS, SaaS,
FaaS y el resto del catálogo), más los cuatro escenarios de clasificación.
"""
from datetime import datetime, timezone
from threading import Lock

import library_catalog
from config.settings import ALLOWED_MODELS
from db.errors import (
    ConceptNotFoundError,
    DuplicateClassificationError,
    InvalidModelError,
)

CATALOGO = library_catalog.soap_catalog()

_lock = Lock()
_clasificadores = {}
_clasificaciones = []
_clientes = {}
_extra_books = {}
_deleted = set()
_next_id = 1


def reset():
    global _next_id
    with _lock:
        _clasificadores.clear()
        _clasificaciones.clear()
        _clientes.clear()
        _extra_books.clear()
        _deleted.clear()
        _next_id = 1


def list_extra_books():
    with _lock:
        return [dict(book) for book in _extra_books.values()]


def deleted_isbns():
    with _lock:
        return set(_deleted)


def _authors(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _optional_number(value, cast):
    if value is None or value == "":
        return None
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def _known(isbn):
    if isbn in _extra_books:
        return True
    return any(book["isbn"] == isbn for book in library_catalog.BOOKS)


def _catalog_book(isbn):
    for book in library_catalog.BOOKS:
        if book["isbn"] == isbn:
            return dict(book)
    return {}


def _concepts_from_catalog(isbn):
    concepts = []
    for item_isbn, name, definition, chapter, page in library_catalog.BOOK_CONCEPTS:
        if item_isbn != isbn:
            continue
        concepts.append(
            {
                "conceptId": library_catalog.CONCEPT_IDS[name],
                "name": name,
                "definition": definition,
                "chapter": chapter,
                "pageNumber": page,
            }
        )
    return concepts


def upsert_book(payload, create=True):
    isbn = str(payload.get("isbn") or "").strip()
    title = str(payload.get("title") or "").strip()
    if not isbn or not title:
        raise ValueError("isbn y title son obligatorios")
    with _lock:
        active = _known(isbn) and isbn not in _deleted
        if create and active:
            raise ValueError("El ISBN ya existe")
        if not create and not active:
            return None
        base = {} if create else dict(_extra_books.get(isbn) or _catalog_book(isbn))
        if "concepts" in payload:
            concepts = payload.get("concepts") or []
        else:
            concepts = base.get("concepts") or _concepts_from_catalog(isbn)
        book = {
            "isbn": isbn,
            "title": title,
            "category": payload["category"] if "category" in payload else (base.get("category") or ""),
            "description": payload["description"] if "description" in payload else (base.get("description") or ""),
            "authors": _authors(payload["authors"]) if "authors" in payload else list(base.get("authors") or []),
            "concepts": concepts,
            "coverUrl": payload.get("coverUrl") or base.get("coverUrl") or f"/covers/{isbn}.svg",
            "genre": payload["genre"] if "genre" in payload else (base.get("genre") or ""),
            "format": payload["format"] if "format" in payload else (base.get("format") or ""),
        }
        if "stock" in payload:
            stock = _optional_number(payload.get("stock"), int)
            if stock is not None:
                book["stock"] = stock
        elif base.get("stock") is not None:
            book["stock"] = base["stock"]
        if "images" in payload:
            book["images"] = payload.get("images") or []
        else:
            book["images"] = base.get("images") or library_catalog.cover_images(title, book["coverUrl"])
        if "publicationYear" in payload:
            year = _optional_number(payload.get("publicationYear"), int)
            if year is not None:
                book["publicationYear"] = year
        elif base.get("publicationYear") is not None:
            book["publicationYear"] = base["publicationYear"]
        if "price" in payload:
            price = _optional_number(payload.get("price"), float)
            if price is not None:
                book["price"] = price
        elif base.get("price") is not None:
            book["price"] = base["price"]
        _deleted.discard(isbn)
        _extra_books[isbn] = book
        return dict(book)


def delete_book(isbn):
    isbn = str(isbn or "").strip()
    with _lock:
        if not isbn or isbn in _deleted or not _known(isbn):
            return False
        _extra_books.pop(isbn, None)
        _deleted.add(isbn)
        return True


def _correo_norm(correo):
    return (correo or "").strip().lower()


def obtener_conceptos_pendientes(correo):
    correo = _correo_norm(correo)
    with _lock:
        hechos = {
            row["concept_id"]
            for row in _clasificaciones
            if row["correo"] == correo
        }
        return [dict(item) for item in CATALOGO if item["concept_id"] not in hechos]


def registrar_clasificacion(nombre, apellidos, correo, concept_id, isbn, modelo, tipo_cliente):
    global _next_id
    correo = _correo_norm(correo)
    if modelo not in ALLOWED_MODELS:
        raise InvalidModelError("El modelo debe ser IaaS, PaaS, SaaS o FaaS")

    match = next(
        (
            item
            for item in CATALOGO
            if item["concept_id"] == int(concept_id) and item["isbn"] == isbn
        ),
        None,
    )
    if match is None:
        raise ConceptNotFoundError("El concepto no existe en el catálogo de la librería")

    with _lock:
        for row in _clasificaciones:
            if row["correo"] == correo and row["concept_id"] == int(concept_id):
                raise DuplicateClassificationError(
                    "El concepto ya fue clasificado por este usuario"
                )
        _clasificadores[correo] = {
            "nombre": nombre,
            "apellidos": apellidos,
            "correo": correo,
        }
        clasificacion_id = _next_id
        _next_id += 1
        _clasificaciones.append(
            {
                "id": clasificacion_id,
                "correo": correo,
                "concept_id": int(concept_id),
                "isbn": isbn,
                "modelo": modelo,
                "tipo_cliente": tipo_cliente,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        _bump_cliente(tipo_cliente, correo)
        return clasificacion_id


def obtener_progreso_usuario(correo):
    correo = _correo_norm(correo)
    total = len(CATALOGO)
    with _lock:
        done = sum(1 for row in _clasificaciones if row["correo"] == correo)
        persona = _clasificadores.get(correo)
        nombre = (
            f"{persona['nombre']} {persona['apellidos']}" if persona else "Sin registros"
        )
        return {
            "correo": correo,
            "nombre_completo": nombre,
            "clasificados": done,
            "pendientes": max(total - done, 0),
            "total_catalogo": total,
        }


def obtener_estadisticas_por_modelo():
    with _lock:
        counts = {modelo: 0 for modelo in ALLOWED_MODELS}
        for row in _clasificaciones:
            counts[row["modelo"]] = counts.get(row["modelo"], 0) + 1
        return [{"modelo": modelo, "cantidad": counts[modelo]} for modelo in ALLOWED_MODELS]


def registrar_cliente_consulta(tipo_cliente, identificador):
    with _lock:
        _bump_cliente(tipo_cliente, identificador)


def _bump_cliente(tipo_cliente, identificador):
    actual = _clientes.get(tipo_cliente, {"peticiones": 0, "identificador": identificador})
    actual["peticiones"] += 1
    actual["identificador"] = identificador
    actual["ultima_peticion"] = datetime.now(timezone.utc).isoformat()
    _clientes[tipo_cliente] = actual
