"""Semáforos y topes sobre el recorrido, y la velocidad a la que hay que llegar.

Cada vehículo tiene su crucero. Al acercarse a un semáforo en rojo frena hasta
detenerse; en un tope baja a paso lento y después vuelve a acelerar.
"""

from __future__ import annotations

import random
import time

from routing import bearing

TOPE_KMH = 16.0
LIGHT_STATES = ("verde", "amarillo", "rojo")


def point_at(points: list[tuple[float, float]], seg_lens: list[float], meters: float) -> tuple[float, float]:
    remain = max(0.0, meters)
    for index, length in enumerate(seg_lens):
        if remain <= length or index == len(seg_lens) - 1:
            fraction = 0.0 if length == 0 else min(1.0, remain / length)
            lat1, lon1 = points[index]
            lat2, lon2 = points[index + 1]
            return (lat1 + (lat2 - lat1) * fraction, lon1 + (lon2 - lon1) * fraction)
        remain -= length
    return points[-1]


class Semaforo:
    def __init__(self, feature_id: str, at_m: float, lat: float, lon: float) -> None:
        self.kind = "semaforo"
        self.id = feature_id
        self.at_m = at_m
        self.lat = lat
        self.lon = lon
        self.green = random.uniform(16, 28)
        self.yellow = 3.0
        self.red = random.uniform(12, 22)
        self.offset = random.uniform(0, self.cycle)
        self.last_state = ""

    @property
    def cycle(self) -> float:
        return self.green + self.yellow + self.red

    def hold_red(self, now: float, seconds: float) -> None:
        """Deja el foco en rojo durante `seconds`, para que el primer alto se vea."""
        self.red = max(self.red, seconds)
        pos = self.green + self.yellow
        self.offset = (pos - (now % self.cycle)) % self.cycle

    def state(self, now: float) -> str:
        moment = (now + self.offset) % self.cycle
        if moment < self.green:
            return "verde"
        if moment < self.green + self.yellow:
            return "amarillo"
        return "rojo"

    def poll(self, now: float) -> str | None:
        state = self.state(now)
        if state == self.last_state:
            return None
        self.last_state = state
        return state

    def mark(self, now: float) -> str:
        state = self.state(now)
        self.last_state = state
        return state

    def describe(self, now: float) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "latitude": round(self.lat, 6),
            "longitude": round(self.lon, 6),
            "state": self.mark(now),
        }


class Tope:
    def __init__(self, feature_id: str, at_m: float, lat: float, lon: float) -> None:
        self.kind = "tope"
        self.id = feature_id
        self.at_m = at_m
        self.lat = lat
        self.lon = lon

    def describe(self, _now: float) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "latitude": round(self.lat, 6),
            "longitude": round(self.lon, 6),
        }


def place_features(vehicle_id: str, points: list[tuple[float, float]], seg_lens: list[float]):
    """Reparte pocos altos por ruta: el primero queda cerca para que se note."""
    total = sum(seg_lens)
    lights_at: list[float] = []
    if total > 180:
        lights_at.append(random.uniform(85, 125))
        cursor = lights_at[0] + random.uniform(520, 760)
        while cursor < total - 140 and len(lights_at) < 6:
            lights_at.append(cursor)
            cursor += random.uniform(520, 760)

    # Un tope donde el rumbo cambia bastante, si no cae encima de un semáforo.
    topes_at: list[float] = []
    cumulative = 0.0
    for index, length in enumerate(seg_lens[:-1]):
        cumulative += length
        if cumulative < 180 or total - cumulative < 80 or len(topes_at) >= 6:
            continue
        if any(abs(cumulative - light) < 80 for light in lights_at):
            continue
        if topes_at and cumulative - topes_at[-1] < 320:
            continue
        turn = _turn(points, index + 1)
        if turn >= 18 or (not topes_at and cumulative > 240):
            topes_at.append(cumulative)

    if total > 280 and not topes_at:
        topes_at.append(min(total - 80, random.uniform(230, 320)))

    now = time.time()
    features = []
    for number, at_m in enumerate(lights_at, start=1):
        lat, lon = point_at(points, seg_lens, at_m)
        light = Semaforo(f"{vehicle_id}-L{number}", at_m, lat, lon)
        if number == 1:
            light.hold_red(now, 24)
        features.append(light)
    for number, at_m in enumerate(topes_at, start=1):
        lat, lon = point_at(points, seg_lens, at_m)
        features.append(Tope(f"{vehicle_id}-T{number}", at_m, lat, lon))
    features.sort(key=lambda item: item.at_m)
    return features


def _turn(points: list[tuple[float, float]], index: int) -> float:
    if index <= 0 or index >= len(points) - 1:
        return 0.0
    before = bearing(points[index - 1], points[index])
    after = bearing(points[index], points[index + 1])
    return abs((after - before + 180) % 360 - 180)


def braking_distance(speed_kmh: float, target_kmh: float, brake_mps2: float) -> float:
    current = max(0.0, speed_kmh) / 3.6
    target = max(0.0, target_kmh) / 3.6
    if current <= target or brake_mps2 <= 0:
        return 0.0
    return (current * current - target * target) / (2 * brake_mps2)


def choose_target(speed_kmh: float, traveled: float, features, brake_mps2: float, cruise_kmh: float, now: float):
    """Devuelve (velocidad deseada, motivo, metros hasta el alto si hay que parar)."""
    chosen = None
    for feature in features:
        distance = feature.at_m - traveled
        if distance < -12:
            continue
        if feature.kind == "tope":
            desired = TOPE_KMH
            if distance > braking_distance(speed_kmh, desired, brake_mps2) + 10 and distance > 18:
                continue
            chosen = _prefer(chosen, (distance, desired, "tope", None))
            continue
        state = feature.state(now)
        if state == "verde":
            continue
        if state == "amarillo" and distance < 16:
            continue
        stop_at = max(0.0, distance - 6)
        if stop_at > braking_distance(speed_kmh, 0, brake_mps2) + 8 and stop_at > 12:
            continue
        chosen = _prefer(chosen, (distance, 0.0, "semaforo", stop_at))
    if chosen is None:
        return cruise_kmh, "crucero", None
    return chosen[1], chosen[2], chosen[3]


def _prefer(current, candidate):
    if current is None:
        return candidate
    # Para primero el alto más exigente (0 km/h gana a un tope). Si empatan, el más cercano.
    if candidate[1] < current[1] - 0.1:
        return candidate
    if abs(candidate[1] - current[1]) <= 0.1 and candidate[0] < current[0]:
        return candidate
    return current
