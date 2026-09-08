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
_next_id = 1


def reset():
    global _next_id
    with _lock:
        _clasificadores.clear()
        _clasificaciones.clear()
        _clientes.clear()
        _extra_books.clear()
        _next_id = 1


def list_extra_books():
    with _lock:
        return [dict(book) for book in _extra_books.values()]


def upsert_book(payload, create=True):
    isbn = str(payload.get("isbn") or "").strip()
    title = str(payload.get("title") or "").strip()
    if not isbn or not title:
        raise ValueError("isbn y title son obligatorios")
    book = {
        "isbn": isbn,
        "title": title,
        "category": payload.get("category") or "",
        "concepts": payload.get("concepts") or [],
    }
    with _lock:
        exists = (
            isbn in _extra_books
            or any(item["isbn"] == isbn for item in CATALOGO)
            or any(book["isbn"] == isbn for book in library_catalog.BOOKS)
        )
        if create and exists:
            raise ValueError("El ISBN ya existe")
        if not create and not exists:
            return None
        _extra_books[isbn] = book
        return dict(book)


def delete_book(isbn):
    with _lock:
        return _extra_books.pop(isbn, None) is not None


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
