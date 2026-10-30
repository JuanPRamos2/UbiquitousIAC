"""Microservicio de usuarios. Puerto 5002.

Administra nombres, roles y contraseñas. El correo identifica la cuenta y no
se modifica. La contraseña se cambia con la actual, la nueva y la confirmación.
Las escrituras exigen JWT. El listado es administrativo.
"""
import logging
import re

import bcrypt
import bootstrap_shared  # noqa: F401
from flask import Flask, jsonify, request

import config
import db
from libreria_platform.redis_store import store
from libreria_platform.web import apply_cors, error, require_bearer

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
logger = logging.getLogger("library_users")

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


def valid_password(password):
    if not password or len(password) < 8:
        return "La contraseña debe tener al menos 8 caracteres."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        return "La contraseña debe incluir letras y números."
    return None


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password, password_hash):
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, AttributeError):
        return False


def same_user(claims, user_id):
    try:
        return int(claims.get("user_id")) == int(user_id)
    except (TypeError, ValueError):
        return False


def db_call(fn):
    try:
        return fn(), None
    except db.Conflict as exc:
        return None, error(str(exc), 409, "CONFLICT")
    except db.Invalid as exc:
        return None, error(str(exc), 400, "INVALID")
    except Exception:
        logger.exception("Fallo de base de datos en users")
        return None, error("La base de datos no está disponible.", 503, "DATABASE_UNAVAILABLE")


def names_from(data, required):
    changes = {}
    mapping = (
        ("first_name", ("first_name", "nombre", "firstName")),
        ("paternal_surname", ("paternal_surname", "apellidoPaterno", "apellido_paterno")),
        ("maternal_surname", ("maternal_surname", "apellidoMaterno", "apellido_materno")),
    )
    for key, aliases in mapping:
        value = pick(data, *aliases)
        present = any(alias in data for alias in aliases)
        if value:
            changes[key] = value
        elif key == "maternal_surname" and (present or required):
            changes[key] = ""
        elif required:
            return None, error(f"Falta {aliases[1]}.", 400, "INVALID")
    if not changes and not required:
        return None, error("No hay datos para actualizar.", 400, "INVALID")
    return changes, None


@app.get("/")
def root():
    return jsonify(
        {
            "service": "users",
            "port": config.PORT,
            "public": [],
            "authenticated": ["GET /users/{id} del propio usuario", "POST /users/{id}/password"],
            "admin": ["GET /users", "POST /users", "PUT /users/{id}", "PATCH /users/{id}", "DELETE /users/{id}"],
        }
    )


@app.get("/health")
def health():
    try:
        postgres_ok = db.ping()
    except Exception:
        postgres_ok = False
    redis_ok = store.ping()
    ready = postgres_ok and redis_ok
    return jsonify(
        {
            "status": "ok" if ready else "error",
            "service": "users",
            "postgres": "ok" if postgres_ok else "error",
            "redis": "ok" if redis_ok else "error",
        }
    ), (200 if ready else 503)


@app.get("/metrics")
def metrics():
    snap = store.snapshot()
    return jsonify({"service": "users", "redis": snap}), (200 if snap.get("connected") else 503)


@app.get("/users")
def list_users():
    _claims, denied = require_bearer(config.JWT_PASSWORD, admin=True)
    if denied:
        return denied
    rows, failed = db_call(db.list_users)
    if failed:
        return failed
    return jsonify({"ok": True, "count": len(rows), "users": rows})


@app.get("/users/<int:user_id>")
def get_user(user_id):
    claims, denied = require_bearer(config.JWT_PASSWORD)
    if denied:
        return denied
    if not same_user(claims, user_id):
        _claims, forbidden = require_bearer(config.JWT_PASSWORD, admin=True)
        if forbidden:
            return error("Rol insuficiente para consultar este usuario.", 403, "FORBIDDEN")
    row, failed = db_call(lambda: db.get_user(user_id))
    if failed:
        return failed
    if not row:
        return error("Usuario no encontrado.", 404, "NOT_FOUND")
    return jsonify({"ok": True, "user": row})


@app.post("/users")
def create_user():
    _claims, denied = require_bearer(config.JWT_PASSWORD, admin=True)
    if denied:
        return denied
    data = payload()
    changes, invalid = names_from(data, required=True)
    if invalid:
        return invalid
    email = pick(data, "email", "correo").lower()
    password = pick(data, "password", "contrasena", "contraseña")
    if not EMAIL_RE.match(email or ""):
        return error("El correo no tiene un formato válido.", 400, "INVALID")
    password_error = valid_password(password)
    if password_error:
        return error(password_error, 400, "INVALID")
    role_name = pick(data, "role", "rol") or "client"
    if role_name not in ("admin", "client"):
        return error("El rol debe ser admin o client.", 400, "INVALID")
    created, failed = db_call(
        lambda: db.insert_user(
            changes["first_name"],
            changes["paternal_surname"],
            changes["maternal_surname"],
            email,
            hash_password(password),
            role_name,
        )
    )
    if failed:
        return failed
    return jsonify({"ok": True, "user": created}), 201


@app.put("/users/<int:user_id>")
def replace_user(user_id):
    return _write_user(user_id, required=True)


@app.patch("/users/<int:user_id>")
def patch_user(user_id):
    return _write_user(user_id, required=False)


def _write_user(user_id, required):
    claims, denied = require_bearer(config.JWT_PASSWORD)
    if denied:
        return denied
    if not same_user(claims, user_id):
        _admin, forbidden = require_bearer(config.JWT_PASSWORD, admin=True)
        if forbidden:
            return error("Rol insuficiente para modificar este usuario.", 403, "FORBIDDEN")
    data = payload()
    if pick(data, "email", "correo"):
        return error(
            "El correo electrónico identifica la cuenta y no se puede cambiar.",
            400,
            "INVALID",
        )
    if pick(data, "password", "contrasena", "newPassword", "currentPassword"):
        return error(
            "La contraseña se cambia con POST /users/{id}/password y tres valores.",
            400,
            "INVALID",
        )
    role_name = pick(data, "role", "rol")
    if role_name and int(claims.get("role_id") or 0) != 1:
        return error("Solo un administrador puede cambiar el rol.", 403, "FORBIDDEN")
    changes, invalid = names_from(data, required=required)
    if invalid and not role_name:
        return invalid
    if changes:
        updated, failed = db_call(lambda: db.update_names(user_id, changes))
        if failed:
            return failed
        if not updated:
            return error("Usuario no encontrado.", 404, "NOT_FOUND")
    else:
        updated, failed = db_call(lambda: db.get_user(user_id))
        if failed:
            return failed
        if not updated:
            return error("Usuario no encontrado.", 404, "NOT_FOUND")
    if role_name:
        updated, failed = db_call(lambda: db.update_role(user_id, role_name))
        if failed:
            return failed
    return jsonify({"ok": True, "user": updated})


@app.delete("/users/<int:user_id>")
def remove_user(user_id):
    claims, denied = require_bearer(config.JWT_PASSWORD, admin=True)
    if denied:
        return denied
    if same_user(claims, user_id):
        return error("Un administrador no puede eliminarse a sí mismo desde este servicio.", 409, "CONFLICT")
    removed, failed = db_call(lambda: db.delete_user(user_id))
    if failed:
        return failed
    if not removed:
        return error("Usuario no encontrado.", 404, "NOT_FOUND")
    return jsonify({"ok": True, "user": removed})


@app.post("/users/<int:user_id>/password")
def change_password(user_id):
    claims, denied = require_bearer(config.JWT_PASSWORD)
    if denied:
        return denied
    if not same_user(claims, user_id):
        return error("Solo el dueño de la cuenta puede cambiar su contraseña.", 403, "FORBIDDEN")
    data = payload()
    current = pick(data, "currentPassword", "contrasenaActual", "password")
    new_password = pick(data, "newPassword", "nuevaContrasena", "nueva_contrasena")
    confirm = pick(data, "confirmPassword", "confirmarContrasena", "confirmar_contrasena")
    if not current or not new_password or not confirm:
        return error(
            "Hacen falta tres contraseñas: la actual, la nueva y la confirmación.",
            400,
            "INVALID",
        )
    if new_password != confirm:
        return error("La confirmación no coincide con la contraseña nueva.", 400, "INVALID")
    password_error = valid_password(new_password)
    if password_error:
        return error(password_error, 400, "INVALID")
    stored, failed = db_call(lambda: db.password_hash(user_id))
    if failed:
        return failed
    if not stored or not check_password(current, stored):
        return error("La contraseña actual no coincide.", 401, "CREDENTIALS_INVALID")
    updated, failed = db_call(lambda: db.update_password(user_id, hash_password(new_password)))
    if failed:
        return failed
    return jsonify({"ok": True, "message": "Contraseña actualizada.", "user": updated})


if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=False)
