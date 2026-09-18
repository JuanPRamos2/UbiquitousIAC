"""Lectura del catálogo de la librería (demo EG02 o PostgreSQL)."""
from config import settings
import library_catalog
from db import demo_store


def _demo_books():
    return library_catalog.books_with_concepts(demo_store.list_extra_books())


def _use_postgres():
    return not settings.SOAP_DEMO


def list_books():
    if _use_postgres():
        try:
            from db import postgres_catalog

            books = postgres_catalog.list_books()
            if books:
                return books
        except Exception:
            pass
    return _demo_books()


def get_book(isbn):
    for book in list_books():
        if book.get("isbn") == isbn:
            return book
    return None


def list_cloud_concepts():
    if _use_postgres():
        try:
            from db import postgres_catalog

            models = postgres_catalog.list_cloud_concepts()
            if models:
                return models
        except Exception:
            pass
    return library_catalog.cloud_concepts_payload()


def list_books_images():
    if _use_postgres():
        try:
            from db import postgres_catalog

            books = postgres_catalog.list_books_images()
            if books:
                return books
        except Exception:
            pass
    return library_catalog.books_with_images(demo_store.list_extra_books())
