"""Comunicación HTTP con los microservicios. No abre bases de datos.

Cada petición se imprime en la consola: cómo se arma, qué se envía y qué contesta
el microservicio. La contraseña no se imprime. El JWT sí, porque es la evidencia
de Authorization: Bearer.
"""
import json
from http.cookiejar import MozillaCookieJar
from urllib import error, parse, request

from config_store import cookie_path, normalize_url, token_path


def refresh_path():
    return token_path().with_name("refresh.txt")


class ApiError(Exception):
    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


def _server_message(payload):
    if not isinstance(payload, dict):
        return ""
    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        return " ".join(str(item) for item in errors)
    for key in ("error", "message"):
        if payload.get(key):
            return str(payload[key])
    return ""


SECRET_KEYS = {
    "password",
    "contrasena",
    "contraseña",
    "currentpassword",
    "newpassword",
    "confirmpassword",
    "confirmarcontrasena",
    "nuevacontrasena",
    "password_hash",
    "token",
    "refreshtoken",
    "refresh_token",
}


def mask_secrets(value):
    if isinstance(value, dict):
        masked = {}
        for key, item in value.items():
            if str(key).lower() in SECRET_KEYS:
                masked[key] = "***"
            else:
                masked[key] = mask_secrets(item)
        return masked
    if isinstance(value, list):
        return [mask_secrets(item) for item in value]
    return value


def authorization_value(token, use_token):
    if not use_token:
        return None
    if not token:
        return None
    return "Bearer " + token


def _evidence_fields(headers, body, payload):
    fields = []
    authorization = ""
    if isinstance(headers, dict):
        authorization = str(headers.get("Authorization") or "")
    if authorization.lower().startswith("bearer "):
        fields.append("Authorization: Bearer ***")
    elif authorization:
        fields.append("Authorization: ***")
    else:
        fields.append("sin Authorization")
    if isinstance(body, dict):
        for key, value in body.items():
            if str(key).lower() in SECRET_KEYS:
                fields.append(f"{key}=***")
            elif key in ("email", "isbn", "title", "nombre"):
                fields.append(f"{key}={value}")
    if isinstance(payload, dict):
        if payload.get("code"):
            fields.append(f"code={payload['code']}")
        if payload.get("tokenType"):
            fields.append(f"tokenType={payload['tokenType']}")
        if payload.get("token") or payload.get("refreshToken"):
            fields.append("token=***")
        if "ok" in payload:
            fields.append(f"ok={payload['ok']}")
        message = _server_message(payload)
        if message and not payload.get("token"):
            fields.append(message)
    return " | ".join(fields)


def format_exchange(method, url, headers, body, status, payload, note):
    return (
        f"evidencia | {method} {url} | {note} | "
        f"{_evidence_fields(headers, body, payload)} | HTTP {status}\n"
    )


def friendly_message(status, payload, method, path):
    server = _server_message(payload)
    if status == 0:
        return server or "El servicio no responde. Revisa la URL en Configuración."
    labels = {
        400: "La petición no es válida.",
        401: "Credenciales incorrectas o la sesión ya no es válida.",
        403: "La cuenta todavía no puede autenticarse o no tiene permiso.",
        404: "No se encontró lo que se pidió.",
        409: "Ese dato ya existe.",
        503: "El servicio está accesible, pero una dependencia no responde.",
    }
    if server:
        return server
    return labels.get(status, f"El servicio respondió HTTP {status} en {method} {path}.")


class HttpClient:
    def __init__(self, login_url, books_url, users_url=None, authors_url=None, pedidos_url=None, pagos_url=None):
        self.login_url = normalize_url(login_url, "http://localhost:5000")
        self.books_url = normalize_url(books_url, "http://localhost:5001")
        self.users_url = normalize_url(users_url or "http://localhost:5002", "http://localhost:5002")
        self.authors_url = normalize_url(authors_url or "http://localhost:5003", "http://localhost:5003")
        self.pedidos_url = normalize_url(pedidos_url or "http://localhost:5004", "http://localhost:5004")
        self.pagos_url = normalize_url(pagos_url or "http://localhost:5005", "http://localhost:5005")
        self.cookie_file = cookie_path()
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
        self.jar = MozillaCookieJar(str(self.cookie_file))
        if self.cookie_file.is_file():
            try:
                self.jar.load(ignore_discard=True, ignore_expires=True)
            except (OSError, ValueError):
                pass
        self.opener = request.build_opener(request.HTTPCookieProcessor(self.jar))
        self.last_exchange = ""
        self.token = ""
        self.refresh_token = ""
        self.token_expires_at = ""
        stored_token = token_path()
        if stored_token.is_file():
            try:
                self.token = stored_token.read_text(encoding="utf-8").strip()
            except OSError:
                self.token = ""
        stored_refresh = refresh_path()
        if stored_refresh.is_file():
            try:
                self.refresh_token = stored_refresh.read_text(encoding="utf-8").strip()
            except OSError:
                self.refresh_token = ""

    def _write_secret(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value + "\n", encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass

    def set_token(self, token, expires_at=""):
        token = (token or "").strip()
        if expires_at:
            self.token_expires_at = str(expires_at)
        if not token or token == self.token:
            return
        self.token = token
        self._write_secret(token_path(), token)
        print("evidencia | JWT guardado | Authorization: Bearer ***\n", flush=True)

    def set_refresh(self, token):
        token = (token or "").strip()
        if not token or token == self.refresh_token:
            return
        self.refresh_token = token
        self._write_secret(refresh_path(), token)

    def clear_token(self):
        self.token = ""
        self.refresh_token = ""
        self.token_expires_at = ""
        for path in (token_path(), refresh_path()):
            if path.is_file():
                try:
                    path.unlink()
                except OSError:
                    pass

    def set_endpoints(self, login_url, books_url, users_url=None, authors_url=None, pedidos_url=None, pagos_url=None):
        self.login_url = normalize_url(login_url, self.login_url)
        self.books_url = normalize_url(books_url, self.books_url)
        if users_url:
            self.users_url = normalize_url(users_url, self.users_url)
        if authors_url:
            self.authors_url = normalize_url(authors_url, self.authors_url)
        if pedidos_url:
            self.pedidos_url = normalize_url(pedidos_url, self.pedidos_url)
        if pagos_url:
            self.pagos_url = normalize_url(pagos_url, self.pagos_url)

    def save_cookies(self):
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
        self.jar.save(ignore_discard=True, ignore_expires=True)

    def clear_cookies(self):
        self.jar.clear()
        self.save_cookies()

    def has_stored_cookies(self):
        return self.cookie_file.is_file() and self.cookie_file.stat().st_size > 0

    def request(self, method, base, path, body=None, headers=None, timeout=8, use_token=False):
        url = base.rstrip("/") + path
        data = None
        hdrs = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        if headers:
            hdrs.update(headers)
        bearer = authorization_value(self.token, use_token)
        if bearer:
            hdrs["Authorization"] = bearer
            note = "Authorization se forma con el JWT guardado: Bearer <token>."
        elif use_token:
            note = "Esta escritura pide JWT, pero el cliente todavía no tiene token."
        else:
            note = "Esta operación es pública: no se envía Authorization."
        req = request.Request(url, data=data, headers=hdrs, method=method)
        status = 0
        payload = {}
        try:
            with self.opener.open(req, timeout=timeout) as response:
                raw = response.read()
                status = response.status
        except error.HTTPError as exc:
            raw = exc.read()
            status = exc.code
        except error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            self.last_exchange = f"{method} {path} → sin conexión"
            print(
                format_exchange(method, url, hdrs, body, "sin conexión", {"error": str(reason)}, note),
                flush=True,
            )
            raise ApiError(f"Sin conexión con {base}. {reason}", 0) from exc
        if raw:
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                self.last_exchange = f"{method} {path} → {status}"
                print(
                    format_exchange(method, url, hdrs, body, status, {"error": "respuesta no JSON"}, note),
                    flush=True,
                )
                raise ApiError(
                    "La respuesta no es JSON. Revisa la URL en Configuración.",
                    status,
                ) from exc
        else:
            payload = {}
        self.last_exchange = f"{method} {path.split('?')[0]} → {status}"
        print(format_exchange(method, url, hdrs, body, status, payload, note), flush=True)
        if status >= 400:
            raise ApiError(friendly_message(status, payload, method, path.split("?")[0]), status)
        if isinstance(payload, dict) and payload.get("token"):
            self.set_token(payload["token"], payload.get("tokenExpiresAt") or "")
        if isinstance(payload, dict) and payload.get("refreshToken"):
            self.set_refresh(payload["refreshToken"])
        return payload

    def probe(self, base, path="/health?format=json"):
        """Distingue servicio sano, degradado e inaccesible. No usa la cookie de sesión."""
        url = base.rstrip("/") + path
        req = request.Request(url, headers={"Accept": "application/json"}, method="GET")
        try:
            with request.urlopen(req, timeout=2) as response:
                raw = response.read()
                status = response.status
        except error.HTTPError as exc:
            raw = exc.read()
            status = exc.code
        except error.URLError:
            return 0, {}
        payload = {}
        if raw:
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                payload = {}
        return status, payload


def query(params):
    clean = {key: value for key, value in params.items() if value not in (None, "")}
    encoded = parse.urlencode(clean)
    return f"?{encoded}" if encoded else ""
