import uuid

from tests.conftest import client as make_client


def xml_ok(response):
    assert response.status_code in (200, 201)
    assert "xml" in response.mimetype
    assert response.data.startswith(b"<?xml")


def test_health_default_xml():
    response = make_client().get("/health")
    xml_ok(response)
    assert b"<health>" in response.data
    assert b"<postgres>" in response.data


def test_health_json():
    payload = make_client().get("/health?format=json").get_json()
    assert payload["format"] == "json"
    assert payload["service"] == "login"
    assert payload["postgres"] == "ok"
    assert payload["_links"]["self"]["href"]


def test_session_anonymous_xml_and_json():
    http = make_client()
    xml_response = http.get("/session")
    xml_ok(xml_response)
    assert b"<authenticated>false</authenticated>" in xml_response.data
    payload = http.get("/session?format=json").get_json()
    assert payload["session"]["authenticated"] is False
    assert payload["session"]["idleTimeoutMinutes"] == 30


def test_login_xml_default_and_json():
    http = make_client()
    xml_response = http.post("/login", json={"email": "nadie@example.com", "password": "x"})
    assert xml_response.status_code == 401
    assert "xml" in xml_response.mimetype
    json_response = http.post(
        "/login?format=json",
        json={"email": "mariana.solis@libreriaonline.mx", "password": "LibreriaAdmin26"},
    )
    assert json_response.status_code == 200
    payload = json_response.get_json()
    assert payload["ok"] is True
    assert payload["user"]["email"] == "mariana.solis@libreriaonline.mx"
    assert payload["user"]["emailVerified"] is True
    assert "password" not in payload["user"]
    assert payload["session"]["authenticated"] is True
    session = http.get("/session?format=json").get_json()
    assert session["session"]["authenticated"] is True
    logout = http.post("/logout?format=json")
    assert logout.get_json()["session"]["authenticated"] is False


def test_register_requires_captcha_and_unique_email():
    http = make_client()
    denied = http.post(
        "/register?format=json",
        json={
            "nombre": "Nueva",
            "apellidoPaterno": "Cuenta",
            "apellidoMaterno": "Demo",
            "email": f"nueva.{uuid.uuid4().hex[:8]}@example.com",
            "password": "ClaveSegura26",
        },
    )
    assert denied.status_code == 400

    challenge = http.get("/captcha?format=json").get_json()
    from captcha import _STORE

    answer = _STORE[challenge["captchaId"]]["answer"]
    email = f"nueva.{uuid.uuid4().hex[:8]}@example.com"
    created = http.post(
        "/register?format=json",
        json={
            "nombre": "Nueva",
            "apellidoPaterno": "Cuenta",
            "apellidoMaterno": "Demo",
            "email": email,
            "password": "ClaveSegura26",
            "captchaId": challenge["captchaId"],
            "captchaAnswer": str(answer),
        },
    )
    assert created.status_code == 201
    payload = created.get_json()
    assert payload["user"]["email"] == email
    assert payload["user"]["first_name"] == "Nueva"
    assert payload["userExists"] is True
    assert payload["emailVerified"] is False
    assert payload["user"]["emailVerified"] is False
    notice = payload["notification"]
    assert notice["code"] == "EMAIL_VERIFICATION_REQUIRED"
    assert notice["channel"] == "json"
    assert notice["userExists"] is True
    assert notice["body"]["verificationToken"]
    token = payload["verificationToken"]
    assert notice["body"]["verificationToken"] == token

    exists = http.get(f"/account?email={email}&format=json")
    assert exists.status_code == 200
    account = exists.get_json()
    assert account["userExists"] is True
    assert account["emailVerified"] is False
    assert account["notification"]["code"] == "USER_EXISTS_UNVERIFIED"

    verified = http.get(f"/verify-email?token={token}&format=json")
    assert verified.status_code == 200
    verified_payload = verified.get_json()
    assert verified_payload["user"]["emailVerified"] is True
    assert verified_payload["notification"]["code"] == "EMAIL_VERIFIED"

    confirmed = http.get(f"/account?email={email}&format=json").get_json()
    assert confirmed["userExists"] is True
    assert confirmed["emailVerified"] is True
    assert confirmed["notification"]["code"] == "USER_EXISTS"

    missing = http.get("/account?email=nadie.existe@example.com&format=json")
    assert missing.status_code == 404
    assert missing.get_json()["userExists"] is False

    challenge2 = http.get("/captcha?format=json").get_json()
    answer2 = _STORE[challenge2["captchaId"]]["answer"]
    duplicate = http.post(
        "/register?format=json",
        json={
            "nombre": "Nueva",
            "apellidoPaterno": "Cuenta",
            "apellidoMaterno": "Demo",
            "email": email,
            "password": "ClaveSegura26",
            "captchaId": challenge2["captchaId"],
            "captchaAnswer": str(answer2),
        },
    )
    assert duplicate.status_code == 409


def test_docs_and_openapi():
    http = make_client()
    docs = http.get("/docs/")
    assert docs.status_code == 200
    spec = http.get("/openapi.yaml")
    assert spec.status_code == 200
    assert b"/login" in spec.data
    assert b"/register" in spec.data
