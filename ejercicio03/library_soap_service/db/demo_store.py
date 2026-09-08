"""Catálogo de demostración para el módulo SOAP cuando no hay PostgreSQL.

Permite ejecutar Flask (local o la página de Ubiquitous) con los mismos
conceptos Cloud del ejercicio, sin alterar el catálogo de la librería.
"""
from datetime import datetime, timezone
from threading import Lock

from config.settings import ALLOWED_MODELS
from db.errors import (
    ConceptNotFoundError,
    DuplicateClassificationError,
    InvalidModelError,
)

CATALOGO = [
    {
        "concept_id": 101,
        "concept_name": "Máquinas virtuales",
        "definition": (
            "Infraestructura con máquinas virtuales, almacenamiento y redes "
            "para instalar el propio sistema operativo."
        ),
        "isbn": "9780132350884",
        "book_title": "Clean Code",
        "category_name": "Tecnología",
    },
    {
        "concept_id": 102,
        "concept_name": "Plataforma de despliegue",
        "definition": (
            "Desplegar la aplicación web sin administrar directamente "
            "servidores ni sistemas operativos."
        ),
        "isbn": "9780132350884",
        "book_title": "Clean Code",
        "category_name": "Tecnología",
    },
    {
        "concept_id": 103,
        "concept_name": "Correo en el navegador",
        "definition": (
            "Los empleados utilizan una aplicación de correo electrónico "
            "desde el navegador con suscripción mensual."
        ),
        "isbn": "9780062316097",
        "book_title": "Sapiens",
        "category_name": "Ciencias sociales",
    },
    {
        "concept_id": 104,
        "concept_name": "Función serverless",
        "definition": (
            "Ejecutar una función automáticamente cada vez que un usuario "
            "suba una imagen al almacenamiento Cloud."
        ),
        "isbn": "9780307474728",
        "book_title": "Cien años de soledad",
        "category_name": "Literatura",
    },
]

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
        exists = isbn in _extra_books or any(item["isbn"] == isbn for item in CATALOGO)
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
