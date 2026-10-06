from datetime import datetime, timedelta, timezone

import jwt

import jwt_auth
from tests.conftest import client as make_client


def test_login_issues_a_token_the_same_service_can_read():
    token, _expires, _jti = jwt_auth.issue_token(
        {"id": 7, "email": "ana@example.com", "role": "client", "role_id": 2}
    )
    claims = jwt_auth.read_bearer("Bearer " + token)
    assert claims["sub"] == "7"
    assert claims["email"] == "ana@example.com"
    assert claims["role"] == "client"
    assert claims["iss"] == "login"


def test_profile_requires_bearer_and_reports_expired_token():
    http = make_client()
    missing = http.patch("/profile?format=json", json={"nombre": "Ana"})
    assert missing.status_code == 401
    assert missing.get_json()["code"] == "TOKEN_MISSING"
    assert "Authorization" in missing.get_json()["error"]

    now = datetime.now(timezone.utc)
    expired_token = jwt.encode(
        {
            "sub": "1",
            "email": "ana@example.com",
            "role": "client",
            "iss": "login",
            "aud": "libreria",
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(minutes=1)).timestamp()),
        },
        jwt_auth.signing_key(),
        algorithm="HS256",
    )
    expired = http.patch(
        "/profile?format=json",
        json={"nombre": "Ana"},
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert expired.status_code == 401
    assert expired.get_json()["code"] == "TOKEN_EXPIRED"

    garbage = http.patch(
        "/profile?format=json",
        json={"nombre": "Ana"},
        headers={"Authorization": "Bearer esto-no-es-un-jwt"},
    )
    assert garbage.status_code == 401
    assert garbage.get_json()["code"] == "TOKEN_INVALID"
