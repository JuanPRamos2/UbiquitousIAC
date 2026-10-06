"""Microservicio de pagos. Puerto 5005.

Registra un pago y deja el pedido en estado pagado. Las lecturas exigen JWT
porque el monto pertenece a un usuario. Borrar un pago es administrativo y
regresa el pedido a pendiente.
"""
import logging

import bootstrap_shared  # noqa: F401
from flask import Flask, jsonify, request

import config
import db
from libreria_platform.jwt_tokens import is_admin
from libreria_platform.redis_store import store
from libreria_platform.web import apply_cors, error, require_bearer

logger = logging.getLogger("library_pagos")
app = Flask(__name__)
apply_cors(app)
_schema = {"ready": False}


def payload():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def pick(data, *names):
    for name in names:
        value = data.get(name)
        if value not in (None, ""):
            return value
    return ""


def ensure():
    if _schema["ready"]:
        return None
    try:
        db.ensure_schema()
    except Exception:
        logger.exception("No se pudo preparar el esquema de pagos")
        return error("La base de datos no está disponible.", 503, "DATABASE_UNAVAILABLE")
    _schema["ready"] = True
    return None


def db_call(fn):
    failed = ensure()
    if failed:
        return None, failed
    try:
        return fn(), None
    except db.Conflict as exc:
        return None, error(str(exc), 409, "CONFLICT")
    except db.Invalid as exc:
        return None, error(str(exc), 400, "INVALID")
    except Exception:
        logger.exception("Fallo de base de datos en pagos")
        return None, error("La base de datos no está disponible.", 503, "DATABASE_UNAVAILABLE")


def owns(claims, row):
    if is_admin(claims):
        return True
    try:
        return int(row["user_id"]) == int(claims.get("user_id"))
    except (TypeError, ValueError, KeyError):
        return False


@app.get("/")
def root():
    return jsonify(
        {
            "service": "pagos",
            "port": config.PORT,
            "note": "Un pago no es una lectura pública.",
            "authenticated": ["GET /pagos", "GET /pagos/{id}", "POST /pagos"],
            "admin": ["PUT /pagos/{id}", "PATCH /pagos/{id}", "DELETE /pagos/{id}"],
        }
    )


@app.get("/health")
def health():
    failed = ensure()
    postgres_ok = failed is None
    if postgres_ok:
        try:
            postgres_ok = db.ping()
        except Exception:
            postgres_ok = False
    redis_ok = store.ping()
    ready = postgres_ok and redis_ok
    return jsonify(
        {
            "status": "ok" if ready else "error",
            "service": "pagos",
            "postgres": "ok" if postgres_ok else "error",
            "redis": "ok" if redis_ok else "error",
        }
    ), (200 if ready else 503)


@app.get("/metrics")
def metrics():
    snap = store.snapshot()
    return jsonify({"service": "pagos", "redis": snap}), (200 if snap.get("connected") else 503)


@app.get("/pagos")
def list_payments():
    claims, denied = require_bearer(config.JWT_PASSWORD)
    if denied:
        return denied
    user_filter = None if is_admin(claims) else int(claims["user_id"])
    rows, failed = db_call(lambda: db.list_payments(user_filter))
    if failed:
        return failed
    return jsonify({"ok": True, "count": len(rows), "pagos": rows})


@app.get("/pagos/<int:payment_id>")
def get_payment(payment_id):
    claims, denied = require_bearer(config.JWT_PASSWORD)
    if denied:
        return denied
    row, failed = db_call(lambda: db.get_payment(payment_id))
    if failed:
        return failed
    if not row:
        return error("Pago no encontrado.", 404, "NOT_FOUND")
    if not owns(claims, row):
        return error("Rol insuficiente para consultar este pago.", 403, "FORBIDDEN")
    return jsonify({"ok": True, "pago": row})


@app.post("/pagos")
def create_payment():
    claims, denied = require_bearer(config.JWT_PASSWORD)
    if denied:
        return denied
    data = payload()
    order_id = pick(data, "order_id", "orderId", "pedido_id", "pedidoId")
    amount = pick(data, "amount", "monto")
    method = str(pick(data, "method", "metodo") or "").strip().lower()
    reference = str(pick(data, "reference", "referencia") or "").strip()
    if order_id in ("", None) or amount in ("", None) or not method:
        return error("Hacen falta pedido, monto y método.", 400, "INVALID")
    if not is_admin(claims):
        order_owner, failed = db_call(
            lambda: __import__("libreria_platform.postgres", fromlist=["query"]).query(
                "SELECT user_id FROM orders WHERE id = %s",
                (int(order_id),),
                fetch="one",
            )
        )
        if failed:
            return failed
        if not order_owner:
            return error("Pedido no encontrado.", 404, "NOT_FOUND")
        if int(order_owner["user_id"]) != int(claims["user_id"]):
            return error("Rol insuficiente para pagar este pedido.", 403, "FORBIDDEN")
    created, failed = db_call(
        lambda: db.register_payment(int(order_id), amount, method, reference)
    )
    if failed:
        return failed
    if not created:
        return error("Pedido no encontrado.", 404, "NOT_FOUND")
    return jsonify({"ok": True, "pago": created}), 201


def _changes(data, required):
    changes = {}
    method = pick(data, "method", "metodo")
    reference = pick(data, "reference", "referencia")
    amount = pick(data, "amount", "monto")
    if method:
        changes["method"] = str(method).strip().lower()
    elif required:
        return None, error("PUT necesita el método.", 400, "INVALID")
    if reference or "reference" in data or "referencia" in data:
        changes["reference"] = str(reference or "") or None
    if amount not in ("", None):
        changes["amount"] = amount
    if not changes:
        return None, error("No hay datos para actualizar.", 400, "INVALID")
    return changes, None


@app.put("/pagos/<int:payment_id>")
def replace_payment(payment_id):
    return _write(payment_id, required=True)


@app.patch("/pagos/<int:payment_id>")
def patch_payment(payment_id):
    return _write(payment_id, required=False)


def _write(payment_id, required):
    _claims, denied = require_bearer(config.JWT_PASSWORD, admin=True)
    if denied:
        return denied
    changes, invalid = _changes(payload(), required)
    if invalid:
        return invalid
    updated, failed = db_call(lambda: db.update_payment(payment_id, changes))
    if failed:
        return failed
    if not updated:
        return error("Pago no encontrado.", 404, "NOT_FOUND")
    return jsonify({"ok": True, "pago": updated})


@app.delete("/pagos/<int:payment_id>")
def remove_payment(payment_id):
    _claims, denied = require_bearer(config.JWT_PASSWORD, admin=True)
    if denied:
        return denied
    removed, failed = db_call(lambda: db.delete_payment(payment_id))
    if failed:
        return failed
    if not removed:
        return error("Pago no encontrado.", 404, "NOT_FOUND")
    return jsonify({"ok": True, "pago": removed})


if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=False)
