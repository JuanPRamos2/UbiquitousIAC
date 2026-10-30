"""Estado de login y books a partir de GET /health."""


def dependency_ok(payload):
    if not isinstance(payload, dict):
        return False
    for key in ("database", "postgres"):
        value = str(payload.get(key) or "").lower()
        if value:
            return value == "ok"
    return str(payload.get("status") or "").lower() == "ok"


def classify(status, payload):
    """up, degraded o down."""
    if not status:
        return "down"
    redis_state = str((payload or {}).get("redis") or "").lower()
    if status == 200 and dependency_ok(payload):
        if redis_state and redis_state != "ok":
            return "degraded"
        return "up"
    return "degraded"


LABELS = {
    "up": "funcionando, base de datos disponible",
    "degraded": "accesible, dependencia degradada",
    "down": "inaccesible",
    "unknown": "sin comprobar",
}


def describe(name, state):
    return f"{name}: {LABELS.get(state, state)}"
