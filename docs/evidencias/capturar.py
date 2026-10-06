"""Captura peticiones y respuestas de los seis microservicios, sin tokens."""

import json
import os
import urllib.error
import urllib.request

BASES = {
    "login": "http://127.0.0.1:5000",
    "books": "http://127.0.0.1:5001",
    "users": "http://127.0.0.1:5002",
    "authors": "http://127.0.0.1:5003",
    "pedidos": "http://127.0.0.1:5004",
    "pagos": "http://127.0.0.1:5005",
}
ISBN = os.environ.get("EVIDENCE_ISBN", "9788420412146")
OUT = []


def call(method, url, body=None, headers=None, label=""):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/json")
    if body is not None:
        request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8", "replace")
            status = response.status
            extra = {
                "X-Cache": response.headers.get("X-Cache"),
                "Content-Type": response.headers.get("Content-Type"),
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        status = exc.code
        extra = {
            "X-Cache": exc.headers.get("X-Cache"),
            "Content-Type": exc.headers.get("Content-Type"),
        }
    parsed = None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = raw[:500]
    record = {
        "label": label,
        "request": f"{method} {url}",
        "status": status,
        "headers": {key: value for key, value in extra.items() if value},
        "body": redact(parsed),
    }
    OUT.append(record)
    print(f"{status} {label}")
    return status, parsed if isinstance(parsed, dict) else {}


def redact(value):
    secret_keys = {
        "token",
        "refreshToken",
        "refresh_token",
        "password",
        "password_hash",
        "currentPassword",
        "newPassword",
        "confirmPassword",
    }
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if key in secret_keys and isinstance(item, str):
                cleaned[key] = "<redactado>"
            else:
                cleaned[key] = redact(item)
        return cleaned
    if isinstance(value, list):
        if len(value) > 3:
            return [redact(item) for item in value[:2]] + [{"_omitidos": len(value) - 2}]
        return [redact(item) for item in value]
    if isinstance(value, str) and value.count(".") == 2 and len(value) > 80:
        return "<jwt-redactado>"
    return value


def main():
    for name, base in BASES.items():
        path = "/health?format=json" if name in ("login", "books") else "/health"
        call("GET", base + path, label=f"health {name}")

    call("GET", BASES["users"] + "/users", label="users sin JWT")
    call("GET", BASES["books"] + "/books?format=json", label="books cache primera lectura")
    call("GET", BASES["books"] + "/books?format=json", label="books cache segunda lectura")
    call("GET", BASES["books"] + f"/books/{ISBN}?format=json", label="book por isbn MISS")
    call("GET", BASES["books"] + f"/books/{ISBN}?format=json", label="book por isbn HIT")
    call("POST", BASES["books"] + "/books", {"title": "sin token"}, label="books POST sin JWT")
    call("GET", BASES["authors"] + "/authors", label="authors publico")

    status, login = call(
        "POST",
        BASES["login"] + "/login?format=json",
        {"email": "mariana.solis@libreriaonline.mx", "password": "LibreriaAdmin26"},
        label="login admin",
    )
    token = login.get("token")
    refresh = login.get("refreshToken")
    user = login.get("user") or {}
    user_id = user.get("id")
    if status != 200 or not token or not user_id:
        raise SystemExit(f"login no entrego token usable: status={status} keys={list(login)}")
    auth = {"Authorization": f"Bearer {token}"}

    call("GET", BASES["login"] + "/metrics?format=json", label="metricas login")
    call("GET", BASES["users"] + "/users", headers=auth, label="users con JWT admin")
    book = call(
        "POST",
        BASES["books"] + "/books?format=json",
        {"isbn": "9780000000999", "title": "Libro evidencia cache"},
        headers=auth,
        label="alta de libro invalida cache",
    )
    call("GET", BASES["books"] + "/books?format=json", label="books cache despues de alta")
    if book[0] == 201:
        call(
            "DELETE",
            BASES["books"] + "/books/9780000000999?format=json",
            headers=auth,
            label="baja del libro de evidencia",
        )
    call(
        "PATCH",
        BASES["users"] + f"/users/{user_id}",
        {"email": "otro@libreriaonline.mx"},
        headers=auth,
        label="rechazo cambio de correo",
    )
    call(
        "POST",
        BASES["users"] + f"/users/{user_id}/password",
        {
            "currentPassword": "LibreriaAdmin26",
            "newPassword": "OtraClave26",
            "confirmPassword": "NoCoincide26",
        },
        headers=auth,
        label="password confirmacion distinta",
    )
    call(
        "PATCH",
        BASES["users"] + f"/users/{user_id}",
        {"maternal_surname": user.get("maternal_surname") or "Solis"},
        headers=auth,
        label="PATCH nombre permitido",
    )

    created_user, _ = call(
        "POST",
        BASES["users"] + "/users",
        {
            "first_name": "Evidencia",
            "paternal_surname": "Redis",
            "maternal_surname": "Jwt",
            "email": "evidencia.redis@libreriaonline.mx",
            "password": "Evidencia26",
            "role": "client",
        },
        headers=auth,
        label="alta de usuario cliente",
    )[1].get("user") or {}, None
    client_id = (created_user or {}).get("id")
    if client_id:
        client_login = call(
            "POST",
            BASES["login"] + "/login?format=json",
            {"email": "evidencia.redis@libreriaonline.mx", "password": "Evidencia26"},
            label="login cliente",
        )[1]
        client_token = client_login.get("token")
        if client_token:
            call(
                "POST",
                BASES["authors"] + "/authors",
                {"full_name": "No debe crearse"},
                headers={"Authorization": f"Bearer {client_token}"},
                label="cliente sin permiso de alta",
            )

    author = call(
        "POST",
        BASES["authors"] + "/authors",
        {"full_name": "Autor Evidencia Redis", "biography": "Creado para la evidencia."},
        headers=auth,
        label="alta de autor",
    )[1].get("author") or {}
    author_id = author.get("id")
    call("GET", BASES["authors"] + "/authors", label="authors cache primera")
    call("GET", BASES["authors"] + "/authors", label="authors cache segunda")
    if author_id:
        call(
            "PATCH",
            BASES["authors"] + f"/authors/{author_id}",
            {"biography": "Biografia actualizada."},
            headers=auth,
            label="PATCH autor",
        )
        call(
            "DELETE",
            BASES["authors"] + f"/authors/{author_id}",
            headers=auth,
            label="DELETE autor",
        )

    call("GET", BASES["pedidos"] + "/pedidos", label="pedidos sin JWT")
    order = call(
        "POST",
        BASES["pedidos"] + "/pedidos",
        {"lines": [{"isbn": ISBN, "quantity": 1}]},
        headers=auth,
        label="crear pedido",
    )[1].get("pedido") or {}
    order_id = order.get("id")
    total = order.get("total")
    call("GET", BASES["pagos"] + "/pagos", headers=auth, label="pagos admin")
    if order_id is not None:
        call(
            "POST",
            BASES["pagos"] + "/pagos",
            {"order_id": order_id, "amount": "1.00", "method": "transferencia", "reference": "mal"},
            headers=auth,
            label="pago con monto incorrecto",
        )
        payment = call(
            "POST",
            BASES["pagos"] + "/pagos",
            {
                "order_id": order_id,
                "amount": total,
                "method": "transferencia",
                "reference": "EVIDENCIA-REDIS",
            },
            headers=auth,
            label="pago correcto",
        )[1].get("pago") or {}
        payment_id = payment.get("id")
        call(
            "PATCH",
            BASES["pedidos"] + f"/pedidos/{order_id}",
            {"status": "cancelado"},
            headers=auth,
            label="cancelar pedido ya pagado",
        )
        if payment_id:
            call(
                "DELETE",
                BASES["pagos"] + f"/pagos/{payment_id}",
                headers=auth,
                label="eliminar pago",
            )
        call(
            "DELETE",
            BASES["pedidos"] + f"/pedidos/{order_id}",
            headers=auth,
            label="cancelar pedido pendiente",
        )

    refreshed = call(
        "POST",
        BASES["login"] + "/token/refresh?format=json",
        {"refreshToken": refresh},
        label="renovar JWT",
    )[1]
    new_token = refreshed.get("token") or token
    fresh = {"Authorization": f"Bearer {new_token}"}
    call(
        "GET",
        BASES["users"] + "/users",
        headers=auth,
        label="JWT anterior revocado al renovar",
    )
    call(
        "GET",
        BASES["pedidos"] + "/pedidos",
        headers=fresh,
        label="token renovado contra pedidos",
    )
    if client_id:
        call(
            "DELETE",
            BASES["users"] + f"/users/{client_id}",
            headers=fresh,
            label="baja del usuario de evidencia",
        )
    call("POST", BASES["login"] + "/logout?format=json", headers=fresh, label="logout")
    call(
        "GET",
        BASES["users"] + "/users",
        headers=fresh,
        label="JWT revocado despues de logout",
    )

    destination = os.path.join(os.path.dirname(__file__), "curl-salida.txt")
    with open(destination, "w", encoding="utf-8") as handle:
        json.dump(OUT, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"escrito {destination} ({len(OUT)} peticiones)")


if __name__ == "__main__":
    main()
