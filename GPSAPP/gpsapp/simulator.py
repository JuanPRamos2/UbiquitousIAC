#!/usr/bin/env python3
"""GPSApp: simula vehículos independientes sobre calles de Monterrey.

Publica posiciones por WebSocket hacia el microservicio (role=gps).
Cada auto tiene su propio origen, destino y velocidad.

    python microservice/app.py
    python gpsapp/simulator.py
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import websocket

from routing import RoutePlanner, bearing, compress, haversine
from traffic import TOPE_KMH, choose_target, place_features


class Cursor:
    """Avanza metros sobre la polilínea de una calle, sin salirse del trazo."""

    def __init__(self, points: list[tuple[float, float]]) -> None:
        self.points = compress(points)
        if len(self.points) < 2:
            raise ValueError("la ruta no tiene suficientes puntos")
        self.seg_lens = [
            haversine(self.points[i], self.points[i + 1]) for i in range(len(self.points) - 1)
        ]
        self.total = sum(self.seg_lens)
        self.index = 0
        self.into = 0.0
        self.traveled = 0.0

    def position(self) -> tuple[float, float]:
        if self.index >= len(self.points) - 1:
            return self.points[-1]
        length = self.seg_lens[self.index]
        if length == 0:
            return self.points[self.index]
        t = self.into / length
        lat1, lon1 = self.points[self.index]
        lat2, lon2 = self.points[self.index + 1]
        return (lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t)

    def advance(self, meters: float) -> bool:
        if meters < 0:
            meters = 0.0
        self.traveled = min(self.total, self.traveled + meters)
        while meters > 0 and self.index < len(self.seg_lens):
            room = self.seg_lens[self.index] - self.into
            if meters < room:
                self.into += meters
                return False
            meters -= room
            self.index += 1
            self.into = 0.0
        self.traveled = self.total
        return True


class Vehicle:
    def __init__(self, vehicle_id: str, route: dict, cruise_kmh: float, accel_mps2: float, brake_mps2: float) -> None:
        self.vehicle_id = vehicle_id
        self.cruise_kmh = cruise_kmh
        self.accel_kmh_s = accel_mps2 * 3.6
        self.brake_mps2 = brake_mps2
        self.brake_kmh_s = brake_mps2 * 3.6
        self.speed_kmh = 0.0
        self.motion = "acelerando"
        self.trip_id = 1
        self.arrived = False
        self.features = []
        self._place(route)

    def _place(self, route: dict) -> None:
        self.route = route
        self.cursor = Cursor(route["points"])
        self.pos = self.cursor.position()
        self.heading = bearing(self.cursor.points[0], self.cursor.points[1])
        self.features = place_features(self.vehicle_id, self.cursor.points, self.cursor.seg_lens)
        self.speed_kmh = 0.0
        self.motion = "acelerando"

    def new_trip(self, route: dict) -> None:
        self.trip_id += 1
        self.arrived = False
        self._place(route)

    def tick(self, dt: float, scale: float) -> None:
        elapsed = dt * scale
        desired, reason, stop_room = choose_target(
            self.speed_kmh,
            self.cursor.traveled,
            self.features,
            self.brake_mps2,
            self.cruise_kmh,
            time.time(),
        )
        self._approach(desired, reason, elapsed)
        step = (self.speed_kmh / 3.6) * elapsed
        if stop_room is not None:
            step = min(step, max(0.0, stop_room))
            if stop_room <= 1.2:
                step = 0.0
                self.speed_kmh = 0.0
                self.motion = "detenido"
        done = self.cursor.advance(step) if step > 0 else self.cursor.traveled >= self.cursor.total
        new_pos = self.cursor.position()
        if haversine(self.pos, new_pos) >= 3:
            self.heading = bearing(self.pos, new_pos)
        self.pos = new_pos
        self.arrived = done

    def _approach(self, desired: float, reason: str, elapsed: float) -> None:
        if self.speed_kmh < desired - 0.3:
            self.speed_kmh = min(desired, self.speed_kmh + self.accel_kmh_s * elapsed)
            self.motion = "acelerando" if self.speed_kmh < self.cruise_kmh - 1.5 else "en crucero"
            return
        if self.speed_kmh > desired + 0.3:
            self.speed_kmh = max(desired, self.speed_kmh - self.brake_kmh_s * elapsed)
            if desired <= 0.4 and self.speed_kmh < 1:
                self.speed_kmh = 0.0
                self.motion = "detenido"
            elif reason == "tope" and self.speed_kmh <= TOPE_KMH + 3:
                self.motion = "en tope"
            else:
                self.motion = "frenando"
            return
        self.speed_kmh = desired
        if desired <= 0.4:
            self.motion = "detenido"
        elif reason == "tope":
            self.motion = "en tope"
        elif self.speed_kmh < self.cruise_kmh - 1.5:
            self.motion = "acelerando"
        else:
            self.motion = "en crucero"

    def payload(self) -> dict:
        lat, lon = self.pos
        return {
            "vehicle_id": self.vehicle_id,
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "speed": round(self.speed_kmh, 1),
            "heading": int(round(self.heading)) % 360,
            "trip_id": self.trip_id,
            "route_name": self.route["name"],
            "streets": self.route.get("summary") or "",
            "motion": self.motion,
        }

    def features_payload(self) -> dict:
        now = time.time()
        return {
            "type": "features",
            "vehicle_id": self.vehicle_id,
            "trip_id": self.trip_id,
            "features": [feature.describe(now) for feature in self.features],
        }

    def signal_changes(self, now: float) -> list[dict]:
        changes = []
        for feature in self.features:
            if feature.kind != "semaforo":
                continue
            state = feature.poll(now)
            if state:
                changes.append({"id": feature.id, "state": state})
        return changes


def connect_and_hello(url: str, scale: float) -> websocket.WebSocket:
    while True:
        try:
            conn = websocket.create_connection(url, timeout=5)
            conn.settimeout(8)
            conn.send(json.dumps({"role": "gps", "time_scale": scale}, ensure_ascii=False))
            hello = json.loads(conn.recv())
            if hello.get("type") == "hello" and hello.get("status") == "ok":
                print(f"Conectado a {url}", flush=True)
                return conn
            print(f"El microservicio respondió: {hello}", flush=True)
            conn.close()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"Esperando al microservicio en {url} ({exc.__class__.__name__})", flush=True)
        time.sleep(1)


def drain(conn: websocket.WebSocket) -> None:
    """Lee avisos del servidor sin bloquear el envío."""
    try:
        conn.settimeout(0.01)
    except Exception:
        return
    try:
        while True:
            raw = conn.recv()
            if not raw:
                break
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "error":
                print(f"Microservicio: {msg.get('message')}", flush=True)
    except Exception:
        return
    finally:
        try:
            conn.settimeout(10)
        except Exception:
            pass


def publish(holder: list, url: str, scale: float, payload: dict) -> None:
    raw = json.dumps(payload, ensure_ascii=False)
    while True:
        try:
            holder[0].send(raw)
            return
        except KeyboardInterrupt:
            raise
        except Exception:
            print("Se cortó el WebSocket. Volviendo a conectar...", flush=True)
            try:
                holder[0].close()
            except Exception:
                pass
            holder[0] = connect_and_hello(url, scale)


def source_label(source: str) -> str:
    if source == "osrm":
        return "OpenStreetMap"
    return "calles guardadas"


def ask_vehicle_count() -> int:
    while True:
        try:
            raw = input("¿Cuántos vehículos quieres mostrar en el mapa? ").strip()
        except EOFError:
            raise SystemExit("Indica el número con -n, por ejemplo: python gpsapp/simulator.py -n 3")
        try:
            count = int(raw)
        except ValueError:
            print("Escribe un número entero.", flush=True)
            continue
        if 1 <= count <= 40:
            return count
        print("Elige entre 1 y 40.", flush=True)


def build_fleet(planner: RoutePlanner, count: int) -> list[Vehicle]:
    workers = 1 if planner.offline or not planner.osrm_ok else min(3, count)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        routes = list(pool.map(lambda _: planner.next_route(), range(count)))
    fleet = []
    # Crucero, aceleración y frenado distintos: no se comportan igual.
    profiles = (
        (30, 1.4, 2.4),
        (38, 1.7, 2.8),
        (46, 2.0, 3.1),
        (54, 2.3, 3.4),
        (62, 2.6, 3.8),
    )
    for index, route in enumerate(routes):
        cruise, accel, brake = profiles[index % len(profiles)]
        cruise += random.uniform(-1.5, 1.5)
        fleet.append(Vehicle(f"V{index + 1:03d}", route, cruise, accel, brake))
    return fleet


def print_plan(fleet: list[Vehicle], url: str, interval: float, scale: float) -> None:
    print(flush=True)
    print("GPSApp  ·  simulador de vehículos en Monterrey", flush=True)
    print(f"Microservicio   {url}", flush=True)
    print(f"Vehículos       {len(fleet)}  (cada uno con su propio recorrido)", flush=True)
    print(f"Envío           cada {interval:.1f} s", flush=True)
    if scale == 1:
        print("Reloj           tiempo real", flush=True)
    else:
        print(f"Reloj           ×{scale:g}   (speed sigue siendo la velocidad del GPS, en km/h)", flush=True)
    print("Calles          © colaboradores de OpenStreetMap", flush=True)
    print(flush=True)
    for vehicle in fleet:
        km = vehicle.cursor.total / 1000
        print(f"  {vehicle.vehicle_id}   {vehicle.route['name']}", flush=True)
        if vehicle.route.get("summary"):
            print(f"         {vehicle.route['summary']}", flush=True)
        lights = sum(1 for feature in vehicle.features if feature.kind == "semaforo")
        bumps = sum(1 for feature in vehicle.features if feature.kind == "tope")
        print(
            f"         {km:.1f} km · crucero {vehicle.cruise_kmh:.0f} km/h · "
            f"{lights} semáforos · {bumps} topes · {source_label(vehicle.route['source'])}",
            flush=True,
        )
    print(flush=True)
    print("Publicando posiciones. Ctrl+C para detener.", flush=True)


def print_status(fleet: list[Vehicle]) -> None:
    print(time.strftime("%H:%M:%S"), flush=True)
    for vehicle in fleet:
        lat, lon = vehicle.pos
        print(
            f"  {vehicle.vehicle_id}  {lat:8.5f}, {lon:9.5f}  "
            f"{vehicle.speed_kmh:4.0f} km/h  {vehicle.motion:<12}  {vehicle.heading:5.0f}°  "
            f"{vehicle.cursor.traveled / 1000:4.1f} km  {vehicle.route['name']}",
            flush=True,
        )


def run(count: int, url: str, interval: float, scale: float, offline: bool) -> None:
    if offline:
        print("Trazando recorridos con las calles de Monterrey guardadas...", flush=True)
    else:
        print("Trazando recorridos por calles de Monterrey (OpenStreetMap)...", flush=True)
    planner = RoutePlanner(offline=offline)
    if not planner.fallbacks:
        print(
            "Aviso: falta gpsapp/fallback_routes.json. "
            "Si OSRM no responde no habrá por dónde circular.",
            flush=True,
        )
    fleet = build_fleet(planner, count)
    print_plan(fleet, url, interval, scale)

    holder = [connect_and_hello(url, scale)]
    try:
        for vehicle in fleet:
            publish(holder, url, scale, vehicle.features_payload())
            publish(holder, url, scale, vehicle.payload())
        next_tick = time.perf_counter()
        last_report = 0.0
        while True:
            signal_batch = []
            now = time.time()
            for vehicle in fleet:
                if vehicle.arrived:
                    route = planner.next_route()
                    print(
                        f"{vehicle.vehicle_id} llegó. Nuevo recorrido: {route['name']}",
                        flush=True,
                    )
                    vehicle.new_trip(route)
                    publish(holder, url, scale, vehicle.features_payload())
                    publish(holder, url, scale, vehicle.payload())
                    continue
                vehicle.tick(interval, scale)
                publish(holder, url, scale, vehicle.payload())
                signal_batch.extend(vehicle.signal_changes(now))
            if signal_batch:
                publish(holder, url, scale, {"type": "signals", "signals": signal_batch})
            drain(holder[0])
            now = time.perf_counter()
            if now - last_report >= 2:
                print_status(fleet)
                last_report = now
            next_tick += interval
            delay = next_tick - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                next_tick = time.perf_counter()
    finally:
        try:
            holder[0].close()
        except Exception:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simula vehículos GPS recorriendo calles distintas de Monterrey.",
        epilog="Arranca antes el microservicio: python microservice/app.py",
    )
    parser.add_argument("-n", "--vehicles", type=int, help="Número de vehículos (1-40)")
    parser.add_argument("--url", default="ws://localhost:5900/ws", help="WebSocket del microservicio")
    parser.add_argument("--interval", type=float, default=0.4, help="Segundos entre cada envío")
    parser.add_argument(
        "--scale",
        type=float,
        default=1,
        help="1 = tiempo real: el auto recorre en el mapa los metros que indica speed. Sube el valor solo si quieres ver el viaje más rápido.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="No consultar OSRM; usar el callejero guardado",
    )
    args = parser.parse_args()
    if args.vehicles is None:
        args.vehicles = ask_vehicle_count()
    if not 1 <= args.vehicles <= 40:
        parser.error("el número de vehículos tiene que estar entre 1 y 40")
    if args.interval < 0.1:
        parser.error("el intervalo mínimo es 0.1 segundos")
    if not 1 <= args.scale <= 40:
        parser.error("la escala tiene que estar entre 1 y 40")
    return args


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    args = parse_args()
    try:
        run(args.vehicles, args.url, args.interval, args.scale, args.offline)
    except KeyboardInterrupt:
        print("\nSimulador detenido.", flush=True)


if __name__ == "__main__":
    main()
