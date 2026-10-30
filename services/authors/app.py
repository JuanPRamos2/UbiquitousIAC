"""Microservicio de autores. Puerto 5003.

GET es público y se cachea. POST, PUT, PATCH y DELETE exigen JWT de administrador.
"""
import json
import logging

import bootstrap_shared  # noqa: F401
from flask import Flask, jsonify, request

import config
import db
from libreria_platform.redis_store import store
from libreria_platform.web import apply_cors, error, require_bearer

logger = logging.getLogger("library_authors")
app = Flask(__name__)
apply_cors(app)


def payload():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def pick(data, *names):
    for name in names:
        value = data.get(name)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def db_call(fn):
    try:
        return fn(), None
    except db.Conflict as exc:
        return None, error(str(exc), 409, "CONFLICT")
    except db.Invalid as exc:
        return None, error(str(exc), 400, "INVALID")
    except Exception:
        logger.exception("Fallo de base de datos en authors")
        return None, error("La base de datos no está disponible.", 503, "DATABASE_UNAVAILABLE")


def cached(key, loader):
    raw = store.get(key, optional=True)
    if raw:
        store.mark_hit()
        try:
            return (json.loads(raw), "HIT"), None
        except json.JSONDecodeError:
            pass
    data, failed = db_call(loader)
    if failed:
        return None, failed
    store.mark_miss()
    store.setex(key, config.CACHE_TTL, json.dumps(data, default=str), optional=True)
    state = "MISS" if store.ping() else "BYPASS"
    return (data, state), None


def invalidate():
    store.delete_pattern("authors:*", optional=True)


@app.get("/")
def root():
    return jsonify(
        {
            "service": "authors",
            "port": config.PORT,
            "public": ["GET /authors", "GET /authors/{id}"],
            "admin": ["POST /authors", "PUT /authors/{id}", "PATCH /authors/{id}", "DELETE /authors/{id}"],
        }
    )


@app.get("/health")
def health():
    try:
        postgres_ok = db.ping()
    except Exception:
        postgres_ok = False
    redis_ok = store.ping()
    return jsonify(
        {
            "status": "ok" if postgres_ok else "error",
            "service": "authors",
            "postgres": "ok" if postgres_ok else "error",
            "redis": "ok" if redis_ok else "error",
        }
    ), (200 if postgres_ok else 503)


@app.get("/metrics")
def metrics():
    snap = store.snapshot()
    return jsonify({"service": "authors", "redis": snap}), (200 if snap.get("connected") else 503)


@app.get("/authors")
def list_authors():
    found, failed = cached("authors:list", db.list_authors)
    if failed:
        return failed
    rows, cache = found
    response = jsonify({"ok": True, "count": len(rows), "authors": rows})
    response.headers["X-Cache"] = cache
    return response


@app.get("/authors/<int:author_id>")
def get_author(author_id):
    found, failed = cached(f"authors:{author_id}", lambda: db.get_author(author_id))
    if failed:
        return failed
    author, cache = found
    if not author:
        return error("Autor no encontrado.", 404, "NOT_FOUND")
    response = jsonify({"ok": True, "author": author})
    response.headers["X-Cache"] = cache
    return response


@app.post("/authors")
def create_author():
    _claims, denied = require_bearer(config.JWT_PASSWORD, admin=True)
    if denied:
        return denied
    data = payload()
    name = pick(data, "full_name", "nombre", "name")
    if not name:
        return error("Falta el nombre del autor.", 400, "INVALID")
    created, failed = db_call(lambda: db.insert_author(name, pick(data, "biography", "biografia")))
    if failed:
        return failed
    invalidate()
    return jsonify({"ok": True, "author": created}), 201


def _changes(data, required):
    changes = {}
    name = pick(data, "full_name", "nombre", "name")
    biography = pick(data, "biography", "biografia")
    if name:
        changes["full_name"] = name
    elif required:
        return None, error("PUT reemplaza el autor y necesita el nombre.", 400, "INVALID")
    if biography or "biography" in data or "biografia" in data:
        changes["biography"] = biography or None
    elif required:
        changes["biography"] = None
    if not changes:
        return None, error("No hay datos para actualizar.", 400, "INVALID")
    return changes, None


@app.put("/authors/<int:author_id>")
def replace_author(author_id):
    return _write(author_id, required=True)


@app.patch("/authors/<int:author_id>")
def patch_author(author_id):
    return _write(author_id, required=False)


def _write(author_id, required):
    _claims, denied = require_bearer(config.JWT_PASSWORD, admin=True)
    if denied:
        return denied
    changes, invalid = _changes(payload(), required)
    if invalid:
        return invalid
    updated, failed = db_call(lambda: db.update_author(author_id, changes))
    if failed:
        return failed
    if not updated:
        return error("Autor no encontrado.", 404, "NOT_FOUND")
    invalidate()
    return jsonify({"ok": True, "author": updated})


@app.delete("/authors/<int:author_id>")
def remove_author(author_id):
    _claims, denied = require_bearer(config.JWT_PASSWORD, admin=True)
    if denied:
        return denied
    removed, failed = db_call(lambda: db.delete_author(author_id))
    if failed:
        return failed
    if not removed:
        return error("Autor no encontrado.", 404, "NOT_FOUND")
    invalidate()
    return jsonify({"ok": True, "author": removed})


@app.post("/authors/<int:author_id>/books")
def link_book(author_id):
    _claims, denied = require_bearer(config.JWT_PASSWORD, admin=True)
    if denied:
        return denied
    data = payload()
    isbn = pick(data, "isbn")
    book_id = data.get("book_id") or data.get("bookId")
    if not isbn and not book_id:
        return error("Indica isbn o book_id.", 400, "INVALID")
    updated, failed = db_call(lambda: db.link_book(author_id, isbn or None, book_id))
    if failed:
        return failed
    if not updated:
        return error("Autor no encontrado.", 404, "NOT_FOUND")
    invalidate()
    return jsonify({"ok": True, "author": updated})


@app.delete("/authors/<int:author_id>/books/<int:book_id>")
def unlink_book(author_id, book_id):
    _claims, denied = require_bearer(config.JWT_PASSWORD, admin=True)
    if denied:
        return denied
    updated, failed = db_call(lambda: db.unlink_book(author_id, book_id))
    if failed:
        return failed
    if not updated:
        return error("Autor no encontrado.", 404, "NOT_FOUND")
    invalidate()
    return jsonify({"ok": True, "author": updated})


if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=False)
