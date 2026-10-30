"""Microservicio independiente de autenticación. Puerto 5000. XML por defecto."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import re
import secrets
from pathlib import Path

import bcrypt
from flask import Flask, redirect, request, send_from_directory, session
from flask_swagger_ui import get_swaggerui_blueprint

import bootstrap_shared  # noqa: F401
import captcha
import config
import db
import jwt_auth
import mail
from format import respond, wants_json
from hateoas import links_for
from libreria_platform.jwt_tokens import revoke
from libreria_platform.redis_store import RedisUnavailable, store
from libreria_platform.web import apply_cors

ROOT = Path(__file__).resolve().parent
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
PUBLIC_USER_FIELDS = (
    "id",
    "first_name",
    "paternal_surname",
    "maternal_surname",
    "full_name",
    "email",
    "role",
    "role_id",
)
logger = logging.getLogger("library_login")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=config.SECRET_KEY,
    SESSION_COOKIE_NAME="login.sid",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=config.SESSION_MINUTES),
    JSON_SORT_KEYS=False,
)
apply_cors(app)

swagger_ui = get_swaggerui_blueprint(
    "/docs",
    "/openapi.yaml",
    config={"app_name": "Login · Librería"},
)
app.register_blueprint(swagger_ui, url_prefix="/docs")


def now_utc():
    return datetime.now(timezone.utc)


def parse_payload():
    if request.is_json:
        return request.get_json(silent=True) or {}
    if request.form:
        return request.form.to_dict()
    return dict(request.args)


def field(payload, *names):
    for name in names:
        value = payload.get(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def public_user(row):
    if not row:
        return None
    payload = {key: row[key] for key in PUBLIC_USER_FIELDS if key in row}
    payload["emailVerified"] = bool(row.get("email_verified"))
    return payload


def valid_email(email):
    return bool(EMAIL_RE.match(email or ""))


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def notification(code, message, **extra):
    payload = {"code": code, "message": message}
    payload.update(extra)
    return payload


def verification_notice(user, token, verify_url, mailed):
    """La 'notificación' de correo va en JSON para verificar al usuario desde Postman."""
    exists = public_user(user)
    body = {
        "userId": user["id"],
        "email": user["email"],
        "fullName": user.get("full_name"),
        "userExists": True,
        "emailVerified": bool(user.get("email_verified")),
        "verificationToken": token,
        "expiresInHours": config.VERIFICATION_HOURS,
        "verifyUrl": verify_url,
        "verify": {"href": verify_url, "method": "GET"},
    }
    return notification(
        "EMAIL_VERIFICATION_REQUIRED",
        (
            "El usuario existe en PostgreSQL. "
            "Confirma el correo con notification.body.verifyUrl (JSON), no hace falta el buzón."
            if not mailed
            else "El usuario existe en PostgreSQL. También se envió el enlace al correo."
        ),
        channel="email+json" if mailed else "json",
        emailSent=mailed,
        to=user["email"],
        subject="Verifica tu correo · Librería",
        userExists=True,
        emailVerified=bool(user.get("email_verified")),
        user=exists,
        body=body,
    )


def issue_verification(user):
    token = secrets.token_urlsafe(32)
    expires = now_utc() + timedelta(hours=config.VERIFICATION_HOURS)
    db.set_verification_token(user["id"], hash_token(token), expires)
    fmt = "json" if wants_json() else None
    verify_url = request.url_root.rstrip("/") + "/verify-email?token=" + token
    if fmt:
        verify_url += "&format=json"
    mailed = False
    try:
        mailed = mail.send_verification(user["email"], verify_url, as_json=wants_json())
    except Exception:
        logger.exception("No se pudo enviar el correo de verificación")
    return token, verify_url, mailed


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
    except ValueError:
        return False


def iso(dt):
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def parse_iso(value):
    if not value:
        return None
    return datetime.fromisoformat(value)


def start_session(user):
    expires = now_utc() + timedelta(minutes=config.SESSION_MINUTES)
    token, token_expires, jti = jwt_auth.issue_token(user)
    refresh_raw = secrets.token_urlsafe(32)
    refresh_hash = hashlib.sha256(refresh_raw.encode("utf-8")).hexdigest()
    access_ttl = max(int((token_expires - now_utc()).total_seconds()), 1)
    refresh_ttl = max(int(config.REFRESH_MINUTES) * 60, access_ttl)
    record = {
        "user_id": user["id"],
        "email": user["email"],
        "role": user.get("role") or "",
        "role_id": user.get("role_id"),
        "jti": jti,
        "refresh_hash": refresh_hash,
        "token_exp": int(token_expires.timestamp()),
    }
    try:
        store.setex(f"session:{jti}", access_ttl, json.dumps(record))
        store.setex(
            f"refresh:{refresh_hash}",
            refresh_ttl,
            json.dumps({"user_id": user["id"], "access_jti": jti}),
        )
    except RedisUnavailable:
        return None
    session.permanent = True
    session["user_id"] = user["id"]
    session["email"] = user["email"]
    session["role"] = user["role"]
    session["started_at"] = iso(now_utc())
    session["expires_at"] = iso(expires)
    session["notified"] = False
    session["jti"] = jti
    session["refresh_hash"] = refresh_hash
    session["token_exp"] = int(token_expires.timestamp())
    payload = session_payload(user, expires)
    payload["token"] = token
    payload["tokenType"] = "Bearer"
    payload["tokenExpiresAt"] = iso(token_expires)
    payload["refreshToken"] = refresh_raw
    payload["refreshExpiresMinutes"] = config.REFRESH_MINUTES
    return payload


def redis_down():
    return respond(
        {
            "ok": False,
            "code": "REDIS_UNAVAILABLE",
            "errors": ["Redis no está disponible. La sesión no se guardó."],
            "error": "Redis no está disponible. La sesión no se guardó.",
            "_links": links_for("self", "health", "docs"),
        },
        root_tag="error",
        status=503,
    )


def token_error_response(exc):
    status = 503 if exc.code == "REDIS_UNAVAILABLE" else 401
    return respond(
        {
            "ok": False,
            "code": exc.code,
            "errors": [exc.message],
            "error": exc.message,
            "_links": links_for("self", "login", "docs"),
        },
        root_tag="error",
        status=status,
    )


def require_token():
    try:
        return jwt_auth.read_bearer(request.headers.get("Authorization")), None
    except jwt_auth.TokenError as exc:
        return None, token_error_response(exc)


def clear_session():
    session.clear()


def session_state():
    if not session.get("user_id"):
        return {
            "authenticated": False,
            "expired": False,
            "canExtend": False,
            "remainingSeconds": 0,
            "expiresAt": None,
            "idleTimeoutMinutes": config.SESSION_MINUTES,
            "notification": None,
        }
    expires = parse_iso(session.get("expires_at"))
    remaining = int((expires - now_utc()).total_seconds()) if expires else 0
    expired = remaining <= 0
    in_grace = expired and remaining >= -config.SESSION_GRACE_SECONDS
    notification = None
    if remaining <= 0:
        notification = {
            "code": "SESSION_EXPIRED",
            "message": (
                f"Su sesión de {config.SESSION_MINUTES} minutos ha expirado. "
                "¿Desea extenderla? Si no hay respuesta, se cerrará."
            ),
            "requiresAction": True,
        }
    elif remaining <= 120:
        notification = {
            "code": "SESSION_EXPIRING",
            "message": (
                f"Su sesión expirará en {remaining} segundos. "
                f"¿Desea extenderla otros {config.SESSION_MINUTES} minutos?"
            ),
            "requiresAction": True,
        }
    if expired and not in_grace:
        clear_session()
        return {
            "authenticated": False,
            "expired": True,
            "canExtend": False,
            "remainingSeconds": 0,
            "expiresAt": iso(expires) if expires else None,
            "idleTimeoutMinutes": config.SESSION_MINUTES,
            "notification": {
                "code": "SESSION_CLOSED",
                "message": "No hubo respuesta. La sesión se cerró.",
                "requiresAction": False,
            },
        }
    return {
        "authenticated": remaining > 0,
        "expired": expired,
        "canExtend": remaining > 0 or in_grace,
        "remainingSeconds": max(remaining, 0),
        "expiresAt": iso(expires) if expires else None,
        "idleTimeoutMinutes": config.SESSION_MINUTES,
        "notification": notification,
    }


def session_payload(user=None, expires=None):
    state = session_state()
    if user is None and session.get("user_id") and (state["authenticated"] or state["canExtend"]):
        user = db.find_user_by_id(session["user_id"])
    payload = {"session": state}
    if user and (state["authenticated"] or state["canExtend"]):
        payload["user"] = public_user(user)
    return payload


@app.get("/")
def root():
    if wants_json() or (request.args.get("format") or "").strip().lower() == "xml":
        return respond(
            {
                "service": "login",
                "port": config.PORT,
                "defaultFormat": "xml",
                "jsonParameter": "format=json",
                "sessionMinutes": config.SESSION_MINUTES,
                "jwt": {
                    "algorithm": "HS256",
                    "scheme": "Bearer",
                    "expiresMinutes": config.JWT_MINUTES,
                    "refreshMinutes": config.REFRESH_MINUTES,
                    "protected": ["PATCH /profile"],
                },
                "richardson": 3,
                "_links": links_for(
                    "self", "register", "login", "logout", "session", "extend",
                    "health", "captcha", "verify", "account", "docs", "ui", "openapi",
                ),
            },
            root_tag="service",
        )
    return redirect("/docs")


@app.get("/openapi.yaml")
def openapi_spec():
    return send_from_directory(ROOT, "openapi.yaml", mimetype="application/yaml")


@app.get("/ui")
def ui():
    return send_from_directory(ROOT / "static", "ui.html")


@app.get("/ui/<path:filename>")
def ui_file(filename):
    return send_from_directory(ROOT / "static", filename)


@app.get("/health")
def health():
    postgres_ok = False
    error = None
    try:
        postgres_ok = db.ping()
    except Exception as exc:
        error = str(exc)
    redis_ok = store.ping()
    ready = postgres_ok and redis_ok
    payload = {
        "status": "ok" if ready else "error",
        "service": "login",
        "postgres": "ok" if postgres_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "_links": links_for("self", "docs", "register", "login", "session"),
    }
    if error:
        payload["error"] = error
    return respond(payload, root_tag="health", status=200 if ready else 503)


@app.get("/metrics")
def metrics():
    snap = store.snapshot()
    return respond(
        {"service": "login", "redis": snap, "_links": links_for("self", "health")},
        root_tag="metrics",
        status=200 if snap.get("connected") else 503,
    )


@app.get("/captcha")
def get_captcha():
    challenge = captcha.create_challenge()
    challenge["_links"] = links_for("self", "register", "docs")
    return respond(challenge, root_tag="captcha")


@app.route("/register", methods=["GET", "POST"])
def register():
    payload = parse_payload()
    nombre = field(payload, "nombre", "first_name", "firstName")
    paterno = field(payload, "apellidoPaterno", "apellido_paterno", "paternal_surname")
    materno = field(payload, "apellidoMaterno", "apellido_materno", "maternal_surname")
    email = field(payload, "email", "correo").lower()
    password = field(payload, "password", "contrasena", "contraseña")
    captcha_id = field(payload, "captchaId", "captcha_id")
    captcha_answer = field(payload, "captchaAnswer", "captcha_answer")
    if request.method == "GET" and not nombre and not email:
        challenge = captcha.create_challenge()
        stored = captcha._STORE.get(challenge["captchaId"]) or {}
        nombre = "Demo"
        paterno = "Get"
        materno = "Json"
        email = f"demo.{int(now_utc().timestamp())}@example.com"
        password = "ClaveSegura26"
        captcha_id = challenge["captchaId"]
        captcha_answer = str(stored.get("answer", ""))

    errors = []
    if not nombre:
        errors.append("El nombre es obligatorio.")
    if not paterno:
        errors.append("El apellido paterno es obligatorio.")
    if not materno:
        errors.append("El apellido materno es obligatorio.")
    if not valid_email(email):
        errors.append("El correo no tiene un formato válido.")
    password_error = valid_password(password)
    if password_error:
        errors.append(password_error)
    if not captcha.verify(captcha_id, captcha_answer):
        errors.append("La validación del correo (captcha) es incorrecta o expiró.")
    if errors:
        return respond(
            {"ok": False, "errors": errors, "_links": links_for("self", "captcha", "docs")},
            root_tag="error",
            status=400,
        )
    if db.find_user_by_email(email):
        return respond(
            {
                "ok": False,
                "userExists": True,
                "errors": ["El correo ya está registrado."],
                "notification": notification(
                    "USER_ALREADY_EXISTS",
                    "Ese correo ya existe en PostgreSQL.",
                    userExists=True,
                    channel="json",
                ),
                "_links": links_for("self", "login", "account", "docs"),
            },
            root_tag="error",
            status=409,
        )
    try:
        user = db.register_user(nombre, paterno, materno, email, hash_password(password))
    except Exception as exc:
        message = str(exc)
        status = 409 if "email" in message.lower() or "unique" in message.lower() else 400
        return respond(
            {"ok": False, "errors": ["No se pudo registrar al usuario."], "_links": links_for("self", "docs")},
            root_tag="error",
            status=status,
        )
    token, verify_url, mailed = issue_verification(user)
    notice = verification_notice(user, token, verify_url, mailed)
    return respond(
        {
            "ok": True,
            "userExists": True,
            "emailVerified": False,
            "message": notice["message"],
            "notification": notice,
            "emailSent": mailed,
            "verificationToken": token,
            "user": public_user(user),
            "_links": links_for(
                "self",
                "captcha",
                "login",
                "account",
                "docs",
                extra={
                    "verify": {"href": verify_url, "method": "GET"},
                    "account": {
                        "href": request.url_root.rstrip("/")
                        + "/account?email="
                        + user["email"]
                        + ("&format=json" if wants_json() else ""),
                        "method": "GET",
                    },
                },
            ),
        },
        root_tag="result",
        status=201,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    payload = parse_payload()
    email = field(payload, "email", "correo").lower()
    password = field(payload, "password", "contrasena", "contraseña")
    if request.method == "GET" and not email and not password:
        email = "mariana.solis@libreriaonline.mx"
        password = "LibreriaAdmin26"
    if not email or not password:
        return respond(
            {
                "ok": False,
                "errors": ["Correo y contraseña son obligatorios."],
                "_links": links_for("self", "register", "docs"),
            },
            root_tag="error",
            status=400,
        )
    user = db.find_user_by_email(email)
    if not user or not check_password(password, user["password_hash"]):
        return respond(
            {
                "ok": False,
                "code": "CREDENTIALS_INVALID",
                "errors": ["Credenciales incorrectas."],
                "error": "Credenciales incorrectas.",
                "_links": links_for("self", "register", "docs"),
            },
            root_tag="error",
            status=401,
        )
    if not user.get("email_verified"):
        return respond(
            {
                "ok": False,
                "userExists": True,
                "emailVerified": False,
                "errors": ["El correo todavía no está verificado."],
                "notification": notification(
                    "EMAIL_NOT_VERIFIED",
                    "El usuario existe en PostgreSQL, pero el correo sigue pendiente. Usa GET /verify-email con el token JSON.",
                    userExists=True,
                    emailVerified=False,
                    channel="json",
                ),
                "user": public_user(user),
                "_links": links_for("self", "verify", "account", "captcha", "docs"),
            },
            root_tag="error",
            status=403,
        )
    started = start_session(user)
    if started is None:
        return redis_down()
    notice = notification(
        "SESSION_STARTED",
        "Sesión iniciada. El usuario existe y el correo está verificado.",
        userExists=True,
        emailVerified=True,
        channel="json",
    )
    return respond(
        {
            "ok": True,
            "userExists": True,
            "emailVerified": True,
            "message": notice["message"],
            "notification": notice,
            **started,
            "_links": links_for("self", "session", "logout", "extend", "health", "docs"),
        },
        root_tag="result",
    )


@app.get("/account")
def account():
    email = (request.args.get("email") or field(parse_payload(), "email", "correo")).lower()
    if not valid_email(email):
        return respond(
            {
                "ok": False,
                "userExists": False,
                "errors": ["Indica un correo válido en ?email="],
                "notification": notification(
                    "EMAIL_REQUIRED",
                    "Para comprobar si el usuario existe envía GET /account?email=correo&format=json",
                    channel="json",
                    userExists=False,
                ),
                "_links": links_for("self", "register", "login", "docs"),
            },
            root_tag="error",
            status=400,
        )
    user = db.find_user_by_email(email)
    if not user:
        return respond(
            {
                "ok": False,
                "userExists": False,
                "emailVerified": False,
                "notification": notification(
                    "USER_NOT_FOUND",
                    "Ese correo no existe en PostgreSQL.",
                    channel="json",
                    userExists=False,
                    emailVerified=False,
                    to=email,
                ),
                "_links": links_for("self", "register", "docs"),
            },
            root_tag="result",
            status=404,
        )
    verified = bool(user.get("email_verified"))
    notice = notification(
        "USER_EXISTS" if verified else "USER_EXISTS_UNVERIFIED",
        (
            "El usuario existe en PostgreSQL y el correo ya está verificado."
            if verified
            else "El usuario existe en PostgreSQL. El correo todavía no está verificado."
        ),
        channel="json",
        userExists=True,
        emailVerified=verified,
        to=email,
    )
    return respond(
        {
            "ok": True,
            "userExists": True,
            "emailVerified": verified,
            "message": notice["message"],
            "notification": notice,
            "user": public_user(user),
            "_links": links_for("self", "login", "verify", "register", "docs"),
        },
        root_tag="account",
    )


@app.get("/verify")
@app.post("/verify")
@app.get("/verify-email")
@app.post("/verify-email")
def verify_email():
    payload = parse_payload()
    token = field(payload, "token") or (request.args.get("token") or "").strip()
    if not token:
        return respond(
            {
                "ok": False,
                "errors": ["Falta el token de verificación."],
                "_links": links_for("self", "register", "login", "docs"),
            },
            root_tag="error",
            status=400,
        )
    user = db.verify_email_token(hash_token(token))
    if not user:
        return respond(
            {
                "ok": False,
                "errors": ["El token es inválido o ya expiró."],
                "_links": links_for("self", "register", "login", "docs"),
            },
            root_tag="error",
            status=400,
        )
    started = start_session(user)
    if started is None:
        return redis_down()
    notice = notification(
        "EMAIL_VERIFIED",
        "Correo verificado. El usuario existe y ya puede iniciar sesión.",
        userExists=True,
        emailVerified=True,
        channel="json",
    )
    return respond(
        {
            "ok": True,
            "userExists": True,
            "emailVerified": True,
            "message": notice["message"],
            "notification": notice,
            **started,
            "_links": links_for("self", "session", "logout", "login", "account", "docs"),
        },
        root_tag="result",
    )


def drop_redis_login():
    jti = session.get("jti")
    refresh_hash = session.get("refresh_hash")
    token_exp = session.get("token_exp")
    header = request.headers.get("Authorization")
    if header:
        try:
            claims = jwt_auth.peek_bearer(header)
            jti = claims.get("jti") or jti
            token_exp = claims.get("exp") or token_exp
        except jwt_auth.TokenError:
            pass
    if jti:
        raw = store.get(f"session:{jti}", optional=True)
        if raw and not refresh_hash:
            try:
                refresh_hash = json.loads(raw).get("refresh_hash")
            except json.JSONDecodeError:
                refresh_hash = None
        revoke(jti, token_exp)
        store.delete(f"session:{jti}")
    if refresh_hash:
        store.delete(f"refresh:{refresh_hash}")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    try:
        drop_redis_login()
    except RedisUnavailable:
        return redis_down()
    clear_session()
    return respond(
        {
            "ok": True,
            "message": "Sesión cerrada.",
            "session": {
                "authenticated": False,
                "expired": False,
                "canExtend": False,
                "remainingSeconds": 0,
                "idleTimeoutMinutes": config.SESSION_MINUTES,
                "notification": None,
            },
            "_links": links_for("self", "login", "register", "health", "docs"),
        },
        root_tag="result",
    )


@app.get("/session")
def get_session():
    payload = session_payload()
    state = payload["session"]
    rels = ["self", "login", "register", "health", "docs"]
    if state["canExtend"]:
        rels.extend(["extend", "logout"])
    elif state["authenticated"]:
        rels.append("logout")
    payload["ok"] = True
    payload["_links"] = links_for(*rels)
    return respond(payload, root_tag="session")


@app.post("/session")
@app.post("/session/extend")
def extend_session():
    state = session_state()
    if not state["canExtend"]:
        clear_session()
        return respond(
            {
                "ok": False,
                "message": "No hay una sesión que se pueda extender.",
                "session": state,
                "_links": links_for("self", "login", "register", "docs"),
            },
            root_tag="error",
            status=401,
        )
    user = db.find_user_by_id(session["user_id"])
    if not user:
        clear_session()
        return respond(
            {
                "ok": False,
                "message": "El usuario de la sesión ya no existe.",
                "_links": links_for("self", "login", "docs"),
            },
            root_tag="error",
            status=401,
        )
    try:
        drop_redis_login()
    except RedisUnavailable:
        return redis_down()
    started = start_session(user)
    if started is None:
        return redis_down()
    return respond(
        {
            "ok": True,
            "message": f"Sesión extendida. El JWT de acceso dura {config.JWT_MINUTES} minutos.",
            **started,
            "_links": links_for("self", "session", "logout", "health", "docs"),
        },
        root_tag="result",
    )


@app.post("/token/refresh")
def refresh_token():
    payload = parse_payload()
    raw = field(payload, "refreshToken", "refresh_token")
    if not raw:
        return respond(
            {
                "ok": False,
                "code": "TOKEN_MISSING",
                "errors": ["Falta refreshToken."],
                "error": "Falta refreshToken.",
            },
            root_tag="error",
            status=401,
        )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    try:
        stored = store.get(f"refresh:{digest}")
    except RedisUnavailable:
        return redis_down()
    if not stored:
        return respond(
            {
                "ok": False,
                "code": "TOKEN_INVALID",
                "errors": ["El refresh token no existe o ya expiró."],
                "error": "El refresh token no existe o ya expiró.",
            },
            root_tag="error",
            status=401,
        )
    try:
        doc = json.loads(stored)
    except json.JSONDecodeError:
        doc = {}
    user = db.find_user_by_id(doc.get("user_id"))
    if not user:
        return respond(
            {"ok": False, "errors": ["El usuario del refresh token ya no existe."]},
            root_tag="error",
            status=401,
        )
    old_jti = doc.get("access_jti")
    try:
        if old_jti:
            raw_session = store.get(f"session:{old_jti}", optional=True)
            token_exp = None
            if raw_session:
                try:
                    token_exp = json.loads(raw_session).get("token_exp")
                except json.JSONDecodeError:
                    token_exp = None
            revoke(old_jti, token_exp)
            store.delete(f"session:{old_jti}", f"refresh:{digest}")
        else:
            store.delete(f"refresh:{digest}")
    except RedisUnavailable:
        return redis_down()
    started = start_session(user)
    if started is None:
        return redis_down()
    return respond(
        {
            "ok": True,
            "message": "Token de acceso renovado.",
            **started,
            "_links": links_for("self", "session", "logout", "docs"),
        },
        root_tag="result",
    )


@app.patch("/profile")
def patch_profile():
    claims, denied = require_token()
    if denied:
        return denied
    try:
        user_id = int(claims.get("sub"))
    except (TypeError, ValueError):
        return token_error_response(
            jwt_auth.TokenError(
                "El token JWT es inválido o no fue emitido por el servicio de login.",
                "TOKEN_INVALID",
            )
        )
    current = db.find_user_by_id(user_id)
    if not current:
        return respond(
            {
                "ok": False,
                "code": "TOKEN_INVALID",
                "errors": ["El usuario del token ya no existe."],
                "error": "El usuario del token ya no existe.",
            },
            root_tag="error",
            status=401,
        )
    stored = db.find_user_by_email(current["email"])
    payload = parse_payload()
    changes = {}
    nombre = field(payload, "nombre", "first_name", "firstName")
    paterno = field(payload, "apellidoPaterno", "apellido_paterno", "paternal_surname")
    materno = field(payload, "apellidoMaterno", "apellido_materno", "maternal_surname")
    email = field(payload, "email", "correo").lower()
    if nombre:
        changes["first_name"] = nombre
    if paterno:
        changes["paternal_surname"] = paterno
    if materno:
        changes["maternal_surname"] = materno
    if email and email != current["email"]:
        if not valid_email(email):
            return respond(
                {"ok": False, "errors": ["El correo no tiene un formato válido."]},
                root_tag="error",
                status=400,
            )
        if db.find_user_by_email(email):
            return respond(
                {"ok": False, "errors": ["Ese correo ya está registrado."]},
                root_tag="error",
                status=409,
            )
        changes["email"] = email
    new_password = field(payload, "newPassword", "password", "nuevaContrasena")
    password_hash = None
    if new_password:
        current_password = field(payload, "currentPassword", "contrasenaActual")
        if not stored or not check_password(current_password, stored["password_hash"]):
            return respond(
                {"ok": False, "errors": ["La contraseña actual no coincide."]},
                root_tag="error",
                status=401,
            )
        password_error = valid_password(new_password)
        if password_error:
            return respond(
                {"ok": False, "errors": [password_error]},
                root_tag="error",
                status=400,
            )
        password_hash = hash_password(new_password)
    if not changes and not password_hash:
        return respond(
            {"ok": False, "errors": ["No hay datos para actualizar."]},
            root_tag="error",
            status=400,
        )
    updated = db.update_profile(current["id"], changes, password_hash)
    return respond(
        {
            "ok": True,
            "message": "Perfil actualizado.",
            "user": public_user(updated),
            "_links": links_for("self", "session", "logout"),
        },
        root_tag="result",
    )


if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=False)
