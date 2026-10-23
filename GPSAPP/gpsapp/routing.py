"""Rutas por calles reales de Monterrey.

Cada vehículo pide un origen y un destino distintos. La geometría sale de
OpenStreetMap a través de OSRM (perfil de auto). Si OSRM no responde, se usa
el callejero guardado en fallback_routes.json, generado con el mismo servicio.
"""

from __future__ import annotations

import json
import math
import random
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

DATA_PATH = Path(__file__).with_name("fallback_routes.json")
USER_AGENT = "MonterreyGPSApp/1.0 (ejercicio academico local)"
OSRM_BASES = (
    "https://router.project-osrm.org",
    "https://routing.openstreetmap.de/routed-car",
)

# El servidor rechaza puntos fuera de esta caja. Las rutas tienen que vivir aquí.
LAT_MIN, LAT_MAX = 25.45, 25.95
LON_MIN, LON_MAX = -100.70, -100.00

LANDMARKS = [
    {"name": "Macroplaza", "lat": 25.6692, "lon": -100.3095},
    {"name": "Parque Fundidora", "lat": 25.6784, "lon": -100.2842},
    {"name": "Barrio Antiguo", "lat": 25.6656, "lon": -100.3072},
    {"name": "Obispado", "lat": 25.6768, "lon": -100.3456},
    {"name": "San Pedro Centro", "lat": 25.6584, "lon": -100.3698},
    {"name": "Calzada del Valle", "lat": 25.6516, "lon": -100.3794},
    {"name": "Valle Oriente", "lat": 25.6404, "lon": -100.3562},
    {"name": "Tec de Monterrey", "lat": 25.6514, "lon": -100.2895},
    {"name": "Contry", "lat": 25.6402, "lon": -100.2784},
    {"name": "Estadio BBVA", "lat": 25.6696, "lon": -100.2446},
    {"name": "Guadalupe Centro", "lat": 25.6772, "lon": -100.2568},
    {"name": "Santa Catarina Centro", "lat": 25.6734, "lon": -100.4576},
    {"name": "Cumbres", "lat": 25.7488, "lon": -100.4065},
    {"name": "Mitras", "lat": 25.7012, "lon": -100.3528},
    {"name": "Hospital Universitario", "lat": 25.6886, "lon": -100.3498},
    {"name": "UANL", "lat": 25.7254, "lon": -100.3124},
    {"name": "San Nicolás Centro", "lat": 25.7412, "lon": -100.3024},
    {"name": "Escobedo Centro", "lat": 25.7938, "lon": -100.3186},
    {"name": "Apodaca Centro", "lat": 25.7802, "lon": -100.1886},
    {"name": "Pueblo Serena", "lat": 25.6035, "lon": -100.2745},
    {"name": "Gonzalitos", "lat": 25.6924, "lon": -100.3568},
    {"name": "Lincoln", "lat": 25.7476, "lon": -100.2865},
    {"name": "Chapultepec", "lat": 25.6638, "lon": -100.3324},
    {"name": "Anáhuac", "lat": 25.7458, "lon": -100.3128},
    {"name": "San Jerónimo", "lat": 25.6915, "lon": -100.3985},
    {"name": "Las Puentes", "lat": 25.7434, "lon": -100.2688},
]

# Pares separados a propósito: cada uno cruza la ciudad por otro lado.
FALLBACK_PAIRS = [
    ("Santa Catarina Centro", "Parque Fundidora"),
    ("Cumbres", "Valle Oriente"),
    ("Escobedo Centro", "Estadio BBVA"),
    ("San Nicolás Centro", "Calzada del Valle"),
    ("UANL", "Contry"),
    ("Apodaca Centro", "San Pedro Centro"),
    ("Mitras", "Guadalupe Centro"),
    ("Lincoln", "Tec de Monterrey"),
    ("Pueblo Serena", "Obispado"),
    ("Anáhuac", "Chapultepec"),
    ("San Jerónimo", "Barrio Antiguo"),
    ("Hospital Universitario", "Apodaca Centro"),
    ("Las Puentes", "Santa Catarina Centro"),
    ("Gonzalitos", "Parque Fundidora"),
    ("Escobedo Centro", "Santa Catarina Centro"),
    ("Valle Oriente", "Lincoln"),
    ("Contry", "San Nicolás Centro"),
    ("Calzada del Valle", "Guadalupe Centro"),
]


class OSRMDown(Exception):
    """Ningún servidor de ruteo respondió."""


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distancia en metros entre dos puntos (lat, lon)."""
    radius = 6_371_000.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Rumbo en grados, 0 = norte, sentido horario. Igual que un GPS."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def tidy_streets(text: str) -> str:
    parts: list[str] = []
    for piece in text.split(","):
        piece = piece.strip()
        if piece and piece not in parts:
            parts.append(piece)
    return ", ".join(parts)


def compress(points: list[tuple[float, float]], min_m: float = 8) -> list[tuple[float, float]]:
    cleaned: list[tuple[float, float]] = []
    for lat, lon in points:
        point = (float(lat), float(lon))
        if not cleaned or haversine(cleaned[-1], point) >= min_m:
            cleaned.append(point)
    return cleaned


def _inside(lat: float, lon: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX


def _quadrant(a: dict, b: dict) -> int:
    deg = bearing((a["lat"], a["lon"]), (b["lat"], b["lon"]))
    return int(deg // 45) % 8


def osrm_route(
    origin: dict,
    dest: dict,
    timeout: float = 4,
) -> tuple[list[tuple[float, float]], str, float] | None:
    """Pide la ruta en auto. None si ese par no tiene camino usable."""
    path = f"{origin['lon']},{origin['lat']};{dest['lon']},{dest['lat']}"
    # steps=true: sin eso OSRM deja vacío el nombre de las calles.
    query = "overview=full&geometries=geojson&steps=true&alternatives=false"
    network_errors = 0
    for base in OSRM_BASES:
        url = f"{base}/route/v1/driving/{path}?{query}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            network_errors += 1
            continue
        if payload.get("code") != "Ok" or not payload.get("routes"):
            continue
        route = payload["routes"][0]
        raw = route.get("geometry", {}).get("coordinates") or []
        points = compress([(lat, lon) for lon, lat in raw])
        distance = float(route.get("distance") or 0)
        if len(points) < 10 or distance < 2_500:
            continue
        inside = sum(1 for lat, lon in points if _inside(lat, lon))
        if inside / len(points) < 0.9:
            continue
        names: list[str] = []
        for leg in route.get("legs") or []:
            text = (leg.get("summary") or "").strip()
            if text and text not in names:
                names.append(text)
        if not names:
            for leg in route.get("legs") or []:
                for step in leg.get("steps") or []:
                    text = (step.get("name") or step.get("ref") or "").strip()
                    if text and text not in names:
                        names.append(text)
                        if len(names) == 4:
                            break
        return points, tidy_streets(", ".join(names)), distance
    if network_errors == len(OSRM_BASES):
        raise OSRMDown("los servidores OSRM no respondieron")
    return None


def load_fallback(path: Path = DATA_PATH) -> list[dict]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw["routes"] if isinstance(raw, dict) else raw
    routes = []
    for row in rows:
        points = compress([(float(lat), float(lon)) for lat, lon in row["points"]])
        if len(points) < 10:
            continue
        inside = sum(1 for lat, lon in points if _inside(lat, lon))
        if inside / len(points) < 0.9:
            continue
        routes.append(
            {
                "name": row["name"],
                "summary": row.get("summary") or "",
                "points": points,
                "source": "local",
            }
        )
    return routes


class RoutePlanner:
    """Reparte recorridos que no repiten el mismo origen y destino."""

    def __init__(self, offline: bool = False) -> None:
        self.offline = offline
        self.osrm_ok = not offline
        self.fallbacks = load_fallback()
        self._lock = threading.Lock()
        self._used_pairs: set[tuple[str, str]] = set()
        self._used_departures: set[tuple[str, int]] = set()
        self._fallback_i = 0
        self._warned_repeat = False
        self._warned_down = False

    def next_route(self) -> dict:
        if self.osrm_ok:
            try:
                route = self._from_osrm(strict=True) or self._from_osrm(strict=False)
            except OSRMDown:
                self._mark_down()
                route = None
            if route:
                return route
        return self._from_file()

    def _mark_down(self) -> None:
        with self._lock:
            first = self.osrm_ok
            self.osrm_ok = False
            warn = first and not self._warned_down
            self._warned_down = True
        if warn:
            print(
                "OSRM no respondió. Los vehículos siguen por calles de Monterrey "
                "guardadas en el proyecto.",
                flush=True,
            )

    def _reserve(self, strict: bool) -> tuple[dict, dict] | None:
        with self._lock:
            for _ in range(50):
                origin, dest = random.sample(LANDMARKS, 2)
                if haversine((origin["lat"], origin["lon"]), (dest["lat"], dest["lon"])) < 4_000:
                    continue
                key = (origin["name"], dest["name"])
                if key in self._used_pairs:
                    continue
                bucket = (origin["name"], _quadrant(origin, dest))
                if strict and bucket in self._used_departures:
                    continue
                self._used_pairs.add(key)
                self._used_departures.add(bucket)
                return origin, dest
        return None

    def _release(self, origin: dict, dest: dict) -> None:
        with self._lock:
            self._used_pairs.discard((origin["name"], dest["name"]))
            self._used_departures.discard((origin["name"], _quadrant(origin, dest)))

    def _from_osrm(self, strict: bool) -> dict | None:
        for _ in range(4):
            pair = self._reserve(strict)
            if pair is None:
                return None
            origin, dest = pair
            try:
                result = osrm_route(origin, dest)
            except OSRMDown:
                self._release(origin, dest)
                raise
            if result is None:
                continue
            points, summary, _distance = result
            return {
                "name": f"{origin['name']} → {dest['name']}",
                "summary": summary,
                "points": points,
                "source": "osrm",
            }
        return None

    def _from_file(self) -> dict:
        with self._lock:
            if not self.fallbacks:
                raise RuntimeError(
                    "No hay calles disponibles. Revisa la red o genera "
                    "gpsapp/fallback_routes.json con: python gpsapp/routing.py --build-fallback"
                )
            index = self._fallback_i
            self._fallback_i += 1
            row = self.fallbacks[index % len(self.fallbacks)]
            wrapped = index >= len(self.fallbacks)
            if wrapped and not self._warned_repeat:
                self._warned_repeat = True
                print(
                    "Aviso: hay más vehículos que recorridos guardados. "
                    "Algunos regresan por la misma calle en sentido contrario.",
                    flush=True,
                )
        points = list(row["points"])
        name = row["name"]
        if wrapped:
            points.reverse()
            left, _, right = name.partition(" → ")
            if right:
                name = f"{right} → {left}"
        return {
            "name": name,
            "summary": row.get("summary") or "",
            "points": points,
            "source": "local",
        }


def build_fallback(path: Path = DATA_PATH) -> None:
    by_name = {place["name"]: place for place in LANDMARKS}
    routes = []
    for origin_name, dest_name in FALLBACK_PAIRS:
        try:
            origin = by_name[origin_name]
            dest = by_name[dest_name]
        except KeyError as exc:
            raise SystemExit(f"Lugar desconocido en FALLBACK_PAIRS: {exc}") from exc
        try:
            result = osrm_route(origin, dest, timeout=8)
        except OSRMDown as exc:
            raise SystemExit(f"No se pudo contactar OSRM: {exc}") from exc
        if result is None:
            print(f"sin ruta  {origin_name} → {dest_name}", flush=True)
            continue
        points, summary, distance = result
        routes.append(
            {
                "name": f"{origin_name} → {dest_name}",
                "summary": summary,
                "distance_m": round(distance),
                "points": [[round(lat, 5), round(lon, 5)] for lat, lon in points],
            }
        )
        print(f"ok  {distance / 1000:5.1f} km  {origin_name} → {dest_name}  {summary}", flush=True)
        time.sleep(0.25)
    document = {
        "city": "Monterrey",
        "source": "OSRM / OpenStreetMap",
        "license": "ODbL, © colaboradores de OpenStreetMap",
        "routes": routes,
    }
    path.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(routes)} recorridos en {path}", flush=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Genera el callejero local de Monterrey con OSRM.")
    parser.add_argument("--build-fallback", action="store_true")
    args = parser.parse_args()
    if not args.build_fallback:
        parser.print_help()
        raise SystemExit(1)
    build_fallback()
