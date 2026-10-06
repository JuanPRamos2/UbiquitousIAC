import secrets
import time
from threading import Lock

_STORE = {}
_LOCK = Lock()
TTL_SECONDS = 10 * 60


def _purge(now):
    expired = [key for key, item in _STORE.items() if item["exp"] <= now]
    for key in expired:
        _STORE.pop(key, None)


def create_challenge():
    left = secrets.randbelow(8) + 2
    right = secrets.randbelow(8) + 1
    captcha_id = secrets.token_urlsafe(12)
    now = time.time()
    with _LOCK:
        _purge(now)
        _STORE[captcha_id] = {"answer": left + right, "exp": now + TTL_SECONDS}
    return {
        "captchaId": captcha_id,
        "question": f"{left} + {right}",
        "expiresInSeconds": TTL_SECONDS,
    }


def verify(captcha_id, answer):
    if not captcha_id:
        return False
    now = time.time()
    with _LOCK:
        _purge(now)
        item = _STORE.pop(str(captcha_id), None)
    if not item:
        return False
    try:
        return int(str(answer).strip()) == int(item["answer"])
    except (TypeError, ValueError):
        return False
