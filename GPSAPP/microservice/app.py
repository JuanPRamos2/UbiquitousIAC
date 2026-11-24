#!/usr/bin/env python3
"""Microservicio de rastreo. Flask + Flask-Sock en 0.0.0.0:5900.

Contrato en ws://localhost:5900/ws
  1. El cliente se identifica: {"role": "gps"} o {"role": "map"}.
  2. GPSApp publica latitude, longitude, speed, heading y vehicle_id.
  3. El mapa recibe un snapshot al entrar y un update por cada posición.

El mapa también va por WebSocket. Preguntar por REST cada segundo llegaría
tarde y cargaría el proceso; aquí el servidor empuja el punto en cuanto entra.
El estado en vivo vive en memoria. El recorrido de cada auto también se
escribe en data/recorridos para no perder por dónde pasó.

    python microservice/app.py
"""

from __future__ import annotations

import copy
import json
import logging
import math
import re
import threading
import time
from pathlib import Path

from flask import Flask, jsonify
from flask_sock import Sock

HOST = "0.0.0.0"
PORT = 5900
MAX_HISTORY = 4000
# Un poco más holgado que el callejero, para no rechazar una curva del periférico.
LAT_MIN, LAT_MAX = 25.40, 26.00
LON_MIN, LON_MAX = -100.80, -99.95
VEHICLE_ID = re.compile(r"[A-Za-z0-9_-]{1,40}")
FEATURE_ID = re.compile(r"[A-Za-z0-9_-]{1,48}")
MOTIONS = {"acelerando", "en crucero", "frenando", "detenido", "en tope"}
LIGHTS = {"verde", "amarillo", "rojo"}

BASE_DIR = Path(__file__).resolve().parent
TRACK_DIR = BASE_DIR.parent / "data" / "recorridos"
app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="/static")
sock = Sock(app)
log = logging.getLogger("gps.tracker")


class MapClient:
    def __init__(self, ws) -> None:
        self.ws = ws
        self.lock = threading.Lock()

    def send(self, raw: str) -> None:
        with self.lock:
            self.ws.send(raw)


class PositionError(ValueError):
    pass


state_lock = threading.Lock()
clients_lock = threading.Lock()
vehicles: dict[str, dict] = {}
road_features: dict[str, dict] = {}
vehicle_features: dict[str, set[str]] = {}
tracks: dict[str, dict] = {}
dirty_tracks: set[str] = set()
map_clients: set[MapClient] = set()
gps_count = 0
time_scale: float | None = None


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    radius = 6_371_000.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def as_float(value, field: str) -> float:
    if isinstance(value, bool) or value is None:
        raise PositionError(f"{field} debe ser numérico")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PositionError(f"{field} debe ser numérico") from exc
    if not math.isfinite(number):
        raise PositionError(f"{field} debe ser numérico")
    return number


def optional_text(msg: dict, key: str, limit: int = 160) -> str:
    value = msg.get(key, "")
    if value is None or value == "":
        return ""
    if not isinstance(value, str):
        raise PositionError(f"{key} debe ser texto")
    cleaned = "".join(ch for ch in value if ch >= " ")
    return cleaned.strip()[:limit]


def validate_position(msg: dict) -> dict:
    if not isinstance(msg, dict):
        raise PositionError("el mensaje debe ser un objeto JSON")
    raw_id = msg.get("vehicle_id")
    if isinstance(raw_id, bool) or not isinstance(raw_id, (str, int)):
        raise PositionError("vehicle_id es obligatorio")
    vehicle_id = str(raw_id).strip()
    if not VEHICLE_ID.fullmatch(vehicle_id):
        raise PositionError("vehicle_id debe usar letras, números, _ o - (máximo 40)")

    lat = as_float(msg.get("latitude"), "latitude")
    lon = as_float(msg.get("longitude"), "longitude")
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        raise PositionError("la coordenada está fuera del área metropolitana de Monterrey")

    speed = as_float(msg.get("speed"), "speed")
    if not 0 <= speed <= 200:
        raise PositionError("speed debe estar entre 0 y 200 km/h")

    heading = as_float(msg.get("heading"), "heading") % 360

    trip_raw = msg.get("trip_id", 1)
    if isinstance(trip_raw, bool):
        raise PositionError("trip_id debe ser numérico")
    try:
        trip_id = int(float(trip_raw))
    except (TypeError, ValueError) as exc:
        raise PositionError("trip_id debe ser numérico") from exc
    if not 0 <= trip_id <= 1_000_000:
        raise PositionError("trip_id fuera de rango")

    return {
        "vehicle_id": vehicle_id,
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "speed": round(speed, 1),
        "heading": int(round(heading)) % 360,
        "trip_id": trip_id,
        "route_name": optional_text(msg, "route_name"),
        "streets": optional_text(msg, "streets"),
        "motion": _motion(msg),
    }


def _motion(msg: dict) -> str:
    text = optional_text(msg, "motion", 24)
    return text if text in MOTIONS else ""


def remember_scale(msg: dict) -> None:
    global time_scale
    if "time_scale" not in msg or msg.get("time_scale") is None:
        return
    scale = as_float(msg.get("time_scale"), "time_scale")
    if not 1 <= scale <= 40:
        raise PositionError("time_scale debe estar entre 1 y 40")
    with state_lock:
        time_scale = scale


def public_view(entry: dict, *, with_history: bool) -> dict:
    view = {
        "vehicle_id": entry["vehicle_id"],
        "latitude": entry["latitude"],
        "longitude": entry["longitude"],
        "speed": entry["speed"],
        "heading": entry["heading"],
        "trip_id": entry["trip_id"],
        "route_name": entry["route_name"],
        "streets": entry["streets"],
        "distance_m": round(entry["distance_m"], 1),
        "motion": entry.get("motion") or "",
    }
    if with_history:
        view["history"] = list(entry["history"])
    return view


def save_position(data: dict) -> tuple[dict, bool, bool]:
    point = [data["latitude"], data["longitude"]]
    with state_lock:
        current = vehicles.get(data["vehicle_id"])
        created = current is None
        new_trip = created or current["trip_id"] != data["trip_id"]
        if new_trip:
            current = {
                "vehicle_id": data["vehicle_id"],
                "latitude": data["latitude"],
                "longitude": data["longitude"],
                "speed": data["speed"],
                "heading": data["heading"],
                "trip_id": data["trip_id"],
                "route_name": data["route_name"],
                "streets": data["streets"],
                "motion": data["motion"],
                "distance_m": 0.0,
                "history": [point],
            }
            vehicles[data["vehicle_id"]] = current
        else:
            delta = haversine_m(
                (current["latitude"], current["longitude"]),
                (data["latitude"], data["longitude"]),
            )
            current["distance_m"] += delta
            current["latitude"] = data["latitude"]
            current["longitude"] = data["longitude"]
            current["speed"] = data["speed"]
            current["heading"] = data["heading"]
            current["route_name"] = data["route_name"]
            current["streets"] = data["streets"]
            current["motion"] = data["motion"]
            if delta >= 8:
                current["history"].append(point)
                if len(current["history"]) > MAX_HISTORY:
                    current["history"] = current["history"][-MAX_HISTORY:]
        note_track(current, new_trip)
        return public_view(current, with_history=False), created, new_trip


def note_track(entry: dict, new_trip: bool) -> None:
    """Anota el punto en memoria. Quien llama ya tiene state_lock."""
    now = time.time()
    vehicle_id = entry["vehicle_id"]
    document = tracks.get(vehicle_id)
    if document is None:
        document = {"vehicle_id": vehicle_id, "trips": []}
        tracks[vehicle_id] = document
    trips = document["trips"]
    opened = new_trip or not trips
    if trips:
        current = trips[-1]
        idle = now - float(current.get("updated_at") or now)
        route_changed = current.get("route_name") != entry["route_name"]
        if idle > 20 or route_changed:
            opened = True
    if opened and trips and trips[-1].get("ended_at") is None:
        trips[-1]["ended_at"] = trips[-1].get("updated_at") or now
    if opened:
        if len(trips) >= 40:
            del trips[:-39]
        trips.append(
            {
                "trip_id": entry["trip_id"],
                "route_name": entry["route_name"],
                "streets": entry["streets"],
                "started_at": now,
                "ended_at": None,
                "updated_at": now,
                "distance_m": 0.0,
                "points": [],
            }
        )
    trip = trips[-1]
    trip["updated_at"] = now
    trip["distance_m"] = round(entry["distance_m"], 1)
    trip["route_name"] = entry["route_name"]
    trip["streets"] = entry["streets"]
    point = [
        entry["latitude"],
        entry["longitude"],
        entry["speed"],
        entry["heading"],
        round(now, 1),
    ]
    previous = trip["points"][-1] if trip["points"] else None
    if _keep_point(previous, point):
        trip["points"].append(point)
        if len(trip["points"]) > 6000:
            trip["points"] = trip["points"][-6000:]
    dirty_tracks.add(vehicle_id)


def _keep_point(previous: list | None, point: list) -> bool:
    if previous is None:
        return True
    moved = haversine_m((previous[0], previous[1]), (point[0], point[1]))
    if moved >= 12:
        return True
    if point[2] < 1 and previous[2] >= 1:
        return True
    return abs(point[2] - previous[2]) >= 10 and moved >= 4


def flush_tracks() -> None:
    with state_lock:
        pending = list(dirty_tracks)
        dirty_tracks.clear()
        copies = {vehicle_id: copy.deepcopy(tracks[vehicle_id]) for vehicle_id in pending if vehicle_id in tracks}
    if not copies:
        return
    TRACK_DIR.mkdir(parents=True, exist_ok=True)
    for vehicle_id, document in copies.items():
        if not VEHICLE_ID.fullmatch(vehicle_id):
            continue
        target = TRACK_DIR / f"{vehicle_id}.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)


def load_tracks() -> None:
    if not TRACK_DIR.exists():
        return
    for path in sorted(TRACK_DIR.glob("*.json")):
        if not VEHICLE_ID.fullmatch(path.stem):
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            log.warning("no se pudo leer %s", path.name)
            continue
        if isinstance(document, dict) and document.get("vehicle_id") == path.stem:
            tracks[path.stem] = document


def track_summary() -> list[dict]:
    with state_lock:
        rows = []
        for vehicle_id in sorted(tracks):
            trips = tracks[vehicle_id].get("trips") or []
            distance = sum(float(trip.get("distance_m") or 0) for trip in trips)
            last = trips[-1] if trips else {}
            rows.append(
                {
                    "vehicle_id": vehicle_id,
                    "trips": len(trips),
                    "distance_m": round(distance, 1),
                    "route_name": last.get("route_name") or "",
                    "updated_at": last.get("updated_at"),
                }
            )
        return rows


def snapshot_payload() -> dict:
    with state_lock:
        views = [public_view(vehicles[key], with_history=True) for key in sorted(vehicles)]
        features = [road_features[key] for key in sorted(road_features)]
        scale = time_scale
    payload: dict = {"type": "snapshot", "vehicles": views, "features": features}
    if scale is not None:
        payload["time_scale"] = scale
    return payload


def encode(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def send_error(ws, message: str) -> None:
    try:
        ws.send(encode({"type": "error", "message": message}))
    except Exception:
        pass


def broadcast(payload: dict) -> None:
    raw = encode(payload)
    with clients_lock:
        targets = list(map_clients)
    dead: list[MapClient] = []
    for client in targets:
        try:
            client.send(raw)
        except Exception:
            dead.append(client)
    if dead:
        with clients_lock:
            for client in dead:
                map_clients.discard(client)


def broadcast_update(view: dict) -> None:
    payload = {"type": "update", **view}
    with state_lock:
        if time_scale is not None:
            payload["time_scale"] = time_scale
    broadcast(payload)


def accept_position(ws, msg: dict) -> None:
    try:
        data = validate_position(msg)
    except PositionError as exc:
        log.warning("rechazado: %s", exc)
        send_error(ws, str(exc))
        return
    view, created, new_trip = save_position(data)
    if created:
        log.info(
            "alta %s  %.5f, %.5f  %s",
            view["vehicle_id"],
            view["latitude"],
            view["longitude"],
            view["route_name"] or "sin ruta",
        )
    elif new_trip:
        log.info("nuevo viaje %s  %s", view["vehicle_id"], view["route_name"] or "sin ruta")
    broadcast_update(view)


def accept_features(msg: dict) -> None:
    vehicle_id = str(msg.get("vehicle_id") or "").strip()
    if not VEHICLE_ID.fullmatch(vehicle_id):
        raise PositionError("vehicle_id es obligatorio")
    raw_items = msg.get("features")
    if not isinstance(raw_items, list) or len(raw_items) > 40:
        raise PositionError("features debe ser una lista de hasta 40 elementos")
    cleaned = [_feature(item, vehicle_id) for item in raw_items]
    with state_lock:
        for feature_id in vehicle_features.get(vehicle_id, set()):
            road_features.pop(feature_id, None)
        ids = set()
        for feature in cleaned:
            road_features[feature["id"]] = feature
            ids.add(feature["id"])
        vehicle_features[vehicle_id] = ids
    broadcast(
        {
            "type": "features",
            "vehicle_id": vehicle_id,
            "trip_id": msg.get("trip_id"),
            "features": cleaned,
        }
    )


def _feature(item: dict, vehicle_id: str) -> dict:
    if not isinstance(item, dict):
        raise PositionError("cada elemento de features debe ser un objeto")
    feature_id = str(item.get("id") or "").strip()
    if not FEATURE_ID.fullmatch(feature_id) or not feature_id.startswith(f"{vehicle_id}-"):
        raise PositionError("id de semáforo o tope inválido")
    kind = item.get("kind")
    if kind not in ("semaforo", "tope"):
        raise PositionError("kind debe ser semaforo o tope")
    lat = as_float(item.get("latitude"), "latitude")
    lon = as_float(item.get("longitude"), "longitude")
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        raise PositionError("el semáforo o tope está fuera de Monterrey")
    feature = {
        "id": feature_id,
        "vehicle_id": vehicle_id,
        "kind": kind,
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
    }
    if kind == "semaforo":
        state = item.get("state") or "rojo"
        if state not in LIGHTS:
            raise PositionError("state del semáforo debe ser verde, amarillo o rojo")
        feature["state"] = state
    return feature


def accept_signals(msg: dict) -> None:
    raw_items = msg.get("signals")
    if not isinstance(raw_items, list):
        raise PositionError("signals debe ser una lista")
    updates = []
    with state_lock:
        for item in raw_items[:80]:
            if not isinstance(item, dict):
                continue
            feature_id = str(item.get("id") or "")
            state = item.get("state")
            feature = road_features.get(feature_id)
            if feature and feature.get("kind") == "semaforo" and state in LIGHTS:
                feature["state"] = state
                updates.append({"id": feature_id, "state": state})
    if updates:
        broadcast({"type": "signals", "signals": updates})


def report_state() -> None:
    beats = 0
    while True:
        time.sleep(2)
        beats += 1
        try:
            flush_tracks()
        except Exception:
            log.exception("no se pudo guardar el recorrido")
        if beats % 3:
            continue
        with state_lock:
            count = len(vehicles)
        with clients_lock:
            maps = len(map_clients)
            gps = gps_count
        if count or maps or gps:
            log.info("estado  vehículos=%s  mapas=%s  gps=%s", count, maps, gps)


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/health")
def health():
    with state_lock:
        ids = sorted(vehicles)
    with clients_lock:
        maps = len(map_clients)
        gps = gps_count
    return jsonify(
        status="ok",
        host=HOST,
        port=PORT,
        vehicles=len(ids),
        vehicle_ids=ids,
        map_clients=maps,
        gps_clients=gps,
        recorridos=len(tracks),
    )


@app.get("/recorridos")
def recorridos():
    return jsonify(folder=str(TRACK_DIR), vehicles=track_summary())


@app.get("/recorridos/<vehicle_id>")
def recorrido(vehicle_id: str):
    if not VEHICLE_ID.fullmatch(vehicle_id):
        return jsonify(error="vehicle_id inválido"), 404
    with state_lock:
        document = copy.deepcopy(tracks.get(vehicle_id))
    if document is None:
        return jsonify(error="sin recorridos"), 404
    return jsonify(document)


@app.get("/favicon.ico")
def favicon():
    return ("", 204)


@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@sock.route("/ws")
def websocket(ws):
    global gps_count
    role = None
    client = None
    try:
        while True:
            raw = ws.receive()
            if raw is None:
                break
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                send_error(ws, "JSON inválido")
                continue
            if not isinstance(msg, dict):
                send_error(ws, "el mensaje debe ser un objeto JSON")
                continue

            if role is None:
                incoming = msg.get("role")
                if incoming == "map":
                    role = "map"
                    client = MapClient(ws)
                    with clients_lock:
                        map_clients.add(client)
                        total = len(map_clients)
                    log.info("mapa conectado (mapas=%s)", total)
                    try:
                        client.send(encode(snapshot_payload()))
                    except Exception:
                        break
                    continue
                if incoming == "gps":
                    try:
                        remember_scale(msg)
                    except PositionError as exc:
                        send_error(ws, str(exc))
                        continue
                    role = "gps"
                    with clients_lock:
                        gps_count += 1
                        total = gps_count
                    log.info("simulador GPS conectado (gps=%s)", total)
                    try:
                        ws.send(encode({"type": "hello", "role": "gps", "status": "ok"}))
                    except Exception:
                        break
                    if "vehicle_id" in msg:
                        accept_position(ws, msg)
                    continue
                send_error(ws, 'primer mensaje: {"role":"gps"} o {"role":"map"}')
                continue

            if role == "gps":
                kind = msg.get("type")
                try:
                    if kind == "features":
                        accept_features(msg)
                    elif kind == "signals":
                        accept_signals(msg)
                    else:
                        accept_position(ws, msg)
                except PositionError as exc:
                    log.warning("rechazado: %s", exc)
                    send_error(ws, str(exc))
    finally:
        if role == "map" and client is not None:
            with clients_lock:
                map_clients.discard(client)
                total = len(map_clients)
            log.info("mapa desconectado (mapas=%s)", total)
        elif role == "gps":
            with clients_lock:
                gps_count = max(0, gps_count - 1)
                total = gps_count
            log.info("simulador GPS desconectado (gps=%s)", total)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    load_tracks()
    threading.Thread(target=report_state, name="estado", daemon=True).start()
    print(f"Microservicio GPS  ·  Flask + Flask-Sock", flush=True)
    print(f"Escuchando en {HOST}:{PORT}", flush=True)
    print(flush=True)
    print(f"  Página web     http://localhost:{PORT}/", flush=True)
    print(f"  WebSocket      ws://localhost:{PORT}/ws", flush=True)
    print(f"  Health check   http://localhost:{PORT}/health", flush=True)
    print(f"  Recorridos     http://localhost:{PORT}/recorridos", flush=True)
    print(flush=True)
    print("Roles: gps (simulador)  ·  map (mapa web)", flush=True)
    print("Mensajes hacia el mapa: snapshot  ·  update", flush=True)
    app.run(host=HOST, port=PORT, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
