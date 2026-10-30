"""Microservicio de pedidos. Puerto 5004.

Las lecturas exigen JWT: un cliente ve los suyos y un administrador ve todos.
Crear, reemplazar líneas, cancelar y borrar también exigen JWT.
El stock baja al crear y regresa al cancelar. El pago lo hace el otro servicio.
"""
import logging

import bootstrap_shared  # noqa: F401
from flask import Flask, jsonify, request

import config
import db
from libreria_platform.jwt_tokens import is_admin
from libreria_platform.redis_store import store
from libreria_platform.web import apply_cors, error, require_bearer

logger = logging.getLogger("library_pedidos")
app = Flask(__name__)
apply_cors(app)
_schema = {"ready": False}


def payload():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def ensure():
    if _schema["ready"]:
        return None
    try:
        db.ensure_schema()
    except Exception:
        logger.exception("No se pudo preparar el esquema de pedidos")
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
        logger.exception("Fallo de base de datos en pedidos")
        return None, error("La base de datos no está disponible.", 503, "DATABASE_UNAVAILABLE")


def owns(claims, order):
    if is_admin(claims):
        return True
    try:
        return int(order["user_id"]) == int(claims.get("user_id"))
    except (TypeError, ValueError, KeyError):
        return False


@app.get("/")
def root():
    return jsonify(
        {
            "service": "pedidos",
            "port": config.PORT,
            "note": "Las lecturas no son públicas: un pedido pertenece a un usuario.",
            "authenticated": ["GET /pedidos", "GET /pedidos/{id}", "POST /pedidos", "PUT /pedidos/{id}", "DELETE /pedidos/{id}"],
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
            "service": "pedidos",
            "postgres": "ok" if postgres_ok else "error",
            "redis": "ok" if redis_ok else "error",
        }
    ), (200 if ready else 503)


@app.get("/metrics")
def metrics():
    snap = store.snapshot()
    return jsonify({"service": "pedidos", "redis": snap}), (200 if snap.get("connected") else 503)


@app.get("/pedidos")
def list_orders():
    claims, denied = require_bearer(config.JWT_PASSWORD)
    if denied:
        return denied
    user_filter = None if is_admin(claims) else int(claims["user_id"])
    rows, failed = db_call(lambda: db.list_orders(user_filter))
    if failed:
        return failed
    return jsonify({"ok": True, "count": len(rows), "pedidos": rows})


@app.get("/pedidos/<int:order_id>")
def get_order(order_id):
    claims, denied = require_bearer(config.JWT_PASSWORD)
    if denied:
        return denied
    order, failed = db_call(lambda: db.get_order(order_id))
    if failed:
        return failed
    if not order:
        return error("Pedido no encontrado.", 404, "NOT_FOUND")
    if not owns(claims, order):
        return error("Rol insuficiente para consultar este pedido.", 403, "FORBIDDEN")
    return jsonify({"ok": True, "pedido": order})


@app.post("/pedidos")
def create_order():
    claims, denied = require_bearer(config.JWT_PASSWORD)
    if denied:
        return denied
    data = payload()
    lines = data.get("lines") or data.get("lineas")
    if not isinstance(lines, list):
        return error("Envía lines con isbn y quantity.", 400, "INVALID")
    user_id = int(claims["user_id"])
    requested = data.get("user_id") or data.get("userId")
    if requested not in (None, ""):
        if not is_admin(claims):
            return error("Solo un administrador puede crear un pedido para otra cuenta.", 403, "FORBIDDEN")
        user_id = int(requested)
    created, failed = db_call(lambda: db.create_order(user_id, lines))
    if failed:
        return failed
    return jsonify({"ok": True, "pedido": created}), 201


@app.put("/pedidos/<int:order_id>")
def replace_order(order_id):
    claims, denied = require_bearer(config.JWT_PASSWORD)
    if denied:
        return denied
    current, failed = db_call(lambda: db.get_order(order_id))
    if failed:
        return failed
    if not current:
        return error("Pedido no encontrado.", 404, "NOT_FOUND")
    if not owns(claims, current):
        return error("Rol insuficiente para modificar este pedido.", 403, "FORBIDDEN")
    lines = payload().get("lines") or payload().get("lineas")
    if not isinstance(lines, list):
        return error("PUT reemplaza las líneas. Envía lines.", 400, "INVALID")
    updated, failed = db_call(lambda: db.replace_lines(order_id, lines))
    if failed:
        return failed
    return jsonify({"ok": True, "pedido": updated})


@app.patch("/pedidos/<int:order_id>")
def patch_order(order_id):
    claims, denied = require_bearer(config.JWT_PASSWORD)
    if denied:
        return denied
    current, failed = db_call(lambda: db.get_order(order_id))
    if failed:
        return failed
    if not current:
        return error("Pedido no encontrado.", 404, "NOT_FOUND")
    if not owns(claims, current):
        return error("Rol insuficiente para modificar este pedido.", 403, "FORBIDDEN")
    status = str(payload().get("status") or payload().get("estado") or "").strip().lower()
    if status != "cancelado":
        return error(
            "PATCH solo acepta status=cancelado. El estado pagado lo registra pagos.",
            400,
            "INVALID",
        )
    updated, failed = db_call(lambda: db.cancel_order(order_id))
    if failed:
        return failed
    return jsonify({"ok": True, "pedido": updated})


@app.delete("/pedidos/<int:order_id>")
def delete_order(order_id):
    claims, denied = require_bearer(config.JWT_PASSWORD)
    if denied:
        return denied
    current, failed = db_call(lambda: db.get_order(order_id))
    if failed:
        return failed
    if not current:
        return error("Pedido no encontrado.", 404, "NOT_FOUND")
    if not owns(claims, current):
        return error("Rol insuficiente para cancelar este pedido.", 403, "FORBIDDEN")
    updated, failed = db_call(lambda: db.cancel_order(order_id))
    if failed:
        return failed
    return jsonify({"ok": True, "pedido": updated})


if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=False)
