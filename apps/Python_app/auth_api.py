"""Autenticación y perfil. Solo habla con el microservicio de login."""
from urllib.parse import quote

from http_api import ApiError


class AuthApi:
    def __init__(self, http):
        self.http = http
        self.user = None

    def _json(self, path):
        separator = "&" if "?" in path else "?"
        return path + separator + "format=json"

    def captcha(self):
        return self.http.request("GET", self.http.login_url, self._json("/captcha"))

    def register(self, nombre, paterno, materno, email, password, captcha_id, captcha_answer):
        payload = self.http.request(
            "POST",
            self.http.login_url,
            self._json("/register"),
            {
                "nombre": nombre,
                "apellidoPaterno": paterno,
                "apellidoMaterno": materno,
                "email": email,
                "password": password,
                "captchaId": captcha_id,
                "captchaAnswer": captcha_answer,
            },
        )
        token = payload.get("verificationToken")
        notice = payload.get("notification") or {}
        body = notice.get("body") if isinstance(notice, dict) else None
        if not token and isinstance(body, dict):
            token = body.get("verificationToken")
        if token:
            verified = self.http.request(
                "GET",
                self.http.login_url,
                self._json(f"/verify?token={quote(token)}"),
            )
            self.user = verified.get("user") or payload.get("user")
            self.http.save_cookies()
            return verified
        self.user = payload.get("user")
        self.http.save_cookies()
        return payload

    def login(self, email, password):
        try:
            payload = self.http.request(
                "POST",
                self.http.login_url,
                self._json("/login"),
                {"email": email.strip(), "password": password},
            )
        except ApiError as exc:
            if exc.status == 403:
                raise ApiError(
                    "La cuenta existe, pero todavía no puede autenticarse. "
                    "El correo sigue sin verificar.",
                    exc.status,
                ) from exc
            if exc.status == 401:
                raise ApiError("Correo o contraseña incorrectos.", exc.status) from exc
            raise
        self.user = payload.get("user")
        self.http.save_cookies()
        return payload

    def logout(self):
        try:
            self.http.request(
                "POST",
                self.http.login_url,
                self._json("/logout"),
                {},
                use_token=True,
            )
        except ApiError:
            pass
        self.user = None
        self.http.clear_token()
        self.http.clear_cookies()

    def session(self):
        payload = self.http.request("GET", self.http.login_url, self._json("/session"))
        state = payload.get("session") or {}
        if state.get("authenticated") and payload.get("user"):
            self.user = payload["user"]
        else:
            self.user = None
        return payload

    def session_active(self):
        try:
            payload = self.session()
        except ApiError:
            return False
        return bool((payload.get("session") or {}).get("authenticated") and self.user)

    def extend(self):
        payload = self.http.request(
            "POST",
            self.http.login_url,
            self._json("/session/extend"),
            {},
            use_token=True,
        )
        if payload.get("user"):
            self.user = payload["user"]
        self.http.save_cookies()
        return payload

    def update_profile(self, changes):
        payload = self.http.request(
            "PATCH",
            self.http.login_url,
            self._json("/profile"),
            changes,
            use_token=True,
        )
        if payload.get("user"):
            self.user = payload["user"]
        return payload
