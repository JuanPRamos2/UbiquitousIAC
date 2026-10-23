/* Mapa web. Se anuncia como role=map y dibuja lo que empuja el microservicio.
   snapshot trae el estado y el historial; update trae solo la posición nueva. */

const COLORS = [
  "#e23d4a",
  "#2f80ed",
  "#1f9d55",
  "#e0a100",
  "#8e4ec6",
  "#0e9aa7",
  "#e07a3d",
  "#3d5afe",
  "#c43d78",
  "#5c9e14",
  "#d35400",
  "#148f77",
];

const CAR_SVG = `<svg viewBox="0 0 24 36" width="16" height="24" aria-hidden="true">
  <rect x="5" y="3" width="14" height="30" rx="6" fill="#fff"/>
  <rect x="7.2" y="7" width="9.6" height="6.2" rx="1.8" fill="#1b3348"/>
  <rect x="6.4" y="15.2" width="11.2" height="5.4" rx="1" fill="#e7eef4"/>
  <rect x="7.2" y="22.6" width="9.6" height="5" rx="1.5" fill="#1b3348" opacity="0.8"/>
</svg>`;

const CENTER = [25.6866, -100.3161];
const fleet = new Map();
const seenAt = new Map();

let framed = false;
let userMoved = false;
let autoMoving = false;
let frameTimer = null;
let activeId = null;
let messages = 0;
let retryMs = 400;
let tileErrors = 0;

const map = L.map("map", { minZoom: 10, maxZoom: 18, zoomControl: true }).setView(CENTER, 12);
map.setMaxBounds(L.latLngBounds([25.35, -100.75], [26.05, -99.9]));

const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(map);
L.control.scale({ imperial: false, position: "bottomleft" }).addTo(map);

tiles.on("tileerror", () => {
  tileErrors += 1;
  if (tileErrors === 6) document.getElementById("tile-warn").hidden = false;
});

map.on("dragstart", () => { if (!autoMoving) userMoved = true; });
map.on("zoomstart", () => {
  document.getElementById("map").classList.add("zooming");
  if (!autoMoving) userMoved = true;
});
map.on("zoomend", () => document.getElementById("map").classList.remove("zooming"));

document.getElementById("ws-url").textContent = `ws://${location.host}/ws`;
document.getElementById("health-url").textContent = `${location.origin}/health`;
document.getElementById("frame").addEventListener("click", () => {
  frameVehicles();
  framed = true;
});
window.addEventListener("resize", () => map.invalidateSize());

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function compass(deg) {
  const dirs = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
  const n = ((Number(deg) % 360) + 360) % 360;
  return dirs[Math.round(n / 45) % 8];
}

function formatDistance(meters) {
  const n = Number(meters) || 0;
  if (n < 1000) return `${Math.round(n)} m`;
  return `${(n / 1000).toFixed(1)} km`;
}

function colorFor() {
  return COLORS[fleet.size % COLORS.length];
}

function setLink(mode) {
  const pill = document.getElementById("live");
  const text = document.getElementById("live-text");
  const state = document.getElementById("link-state");
  pill.classList.remove("wait", "live", "down");
  pill.classList.add(mode);
  if (mode === "live") {
    text.textContent = "En vivo";
    state.textContent = "En vivo";
  } else if (mode === "down") {
    text.textContent = "Reconectando…";
    state.textContent = "Sin conexión";
  } else {
    text.textContent = "Conectando…";
    state.textContent = "Conectando…";
  }
}

function showScale(scale) {
  const el = document.getElementById("scale");
  if (!scale || scale <= 1) {
    el.textContent = "Tiempo real";
    return;
  }
  el.textContent = `Reloj ×${scale}`;
}

function noteMessage(msg) {
  messages += 1;
  document.getElementById("msg-count").textContent = String(messages);
  const last = document.getElementById("last-msg");
  if (msg.type === "snapshot") {
    last.textContent = `snapshot · ${msg.vehicles.length}`;
  } else if (msg.type === "update") {
    last.textContent = `update · ${msg.vehicle_id}`;
  } else {
    last.textContent = msg.type || "mensaje";
  }
  if (msg.time_scale) showScale(msg.time_scale);
}

function makeIcon(color, heading) {
  return L.divIcon({
    className: "veh-icon",
    html: `<div class="veh" style="background:${color}"><div class="veh-rot" style="transform:rotate(${Number(heading) || 0}deg)">${CAR_SVG}</div></div>`,
    iconSize: [36, 36],
    iconAnchor: [18, 18],
    popupAnchor: [0, -18],
  });
}

function popupHtml(data) {
  const streets = data.streets ? `<br>${esc(data.streets)}` : "";
  const route = data.route_name || "Monterrey";
  return `<strong>${esc(data.vehicle_id)}</strong><br>${esc(route)}${streets}<br>${Number(data.speed).toFixed(1)} km/h · ${compass(data.heading)} ${Math.round(data.heading)}°`;
}

function aim(marker, heading) {
  const icon = marker.getElement();
  const rot = icon && icon.querySelector(".veh-rot");
  if (rot) rot.style.transform = `rotate(${Number(heading) || 0}deg)`;
}

function removeVehicle(id) {
  const rec = fleet.get(id);
  if (!rec) return;
  map.removeLayer(rec.marker);
  map.removeLayer(rec.line);
  map.removeLayer(rec.casing);
  rec.card.remove();
  fleet.delete(id);
  seenAt.delete(id);
  if (activeId === id) activeId = null;
}

function renderCard(rec) {
  const data = rec.data;
  rec.card.querySelector(".vid").textContent = data.vehicle_id;
  rec.card.querySelector(".speed").textContent = `${Number(data.speed).toFixed(0)} km/h`;
  rec.card.querySelector(".route").textContent = data.route_name || "Recorrido en Monterrey";
  const streets = rec.card.querySelector(".streets");
  streets.textContent = data.streets || "";
  streets.hidden = !data.streets;
  const stale = rec.card.classList.contains("stale") ? " · sin señal" : "";
  rec.card.querySelector(".meta").textContent =
    `${Number(data.latitude).toFixed(5)}, ${Number(data.longitude).toFixed(5)} · ${compass(data.heading)} ${Math.round(data.heading)}° · ${formatDistance(data.distance_m)}${stale}`;
  rec.card.title = [data.route_name, data.streets].filter(Boolean).join(" · ");
}

function ensure(data) {
  const id = data.vehicle_id;
  if (fleet.has(id)) return fleet.get(id);
  const color = colorFor();
  const card = document.createElement("button");
  card.type = "button";
  card.className = "card";
  card.style.setProperty("--c", color);
  card.innerHTML = `<strong class="vid"></strong><span class="speed"></span><span class="route"></span><span class="streets"></span><span class="meta"></span>`;
  card.addEventListener("click", () => focusVehicle(id));
  const casing = L.polyline([], { color: "#ffffff", weight: 8, opacity: 0.9, lineCap: "round", lineJoin: "round" }).addTo(map);
  const line = L.polyline([], { color, weight: 4, opacity: 0.95, lineCap: "round", lineJoin: "round" }).addTo(map);
  const marker = L.marker([data.latitude, data.longitude], {
    icon: makeIcon(color, data.heading),
    zIndexOffset: 400,
    riseOnHover: true,
  }).addTo(map);
  marker.on("click", () => focusVehicle(id, false));
  const rec = { id, color, card, marker, line, casing, data, history: [] };
  fleet.set(id, rec);
  orderCards();
  return rec;
}

function orderCards() {
  const box = document.getElementById("cards");
  for (const id of [...fleet.keys()].sort()) box.appendChild(fleet.get(id).card);
}

function focusVehicle(id, pan = true) {
  const rec = fleet.get(id);
  if (!rec) return;
  activeId = id;
  for (const item of fleet.values()) {
    item.card.classList.toggle("active", item.id === id);
    item.card.setAttribute("aria-pressed", item.id === id ? "true" : "false");
  }
  rec.card.scrollIntoView({ block: "nearest" });
  if (pan) map.panTo([rec.data.latitude, rec.data.longitude], { animate: true });
  rec.marker.bindPopup(popupHtml(rec.data)).openPopup();
}

function applyHistory(rec, history) {
  rec.history = history;
  rec.casing.setLatLngs(history);
  rec.line.setLatLngs(history);
}

function upsert(data, resetHistory) {
  const rec = ensure(data);
  const sameTrip = rec.data && rec.data.trip_id === data.trip_id && rec.history.length;
  let history;
  if (resetHistory) {
    history = Array.isArray(data.history) && data.history.length
      ? data.history.map((point) => [Number(point[0]), Number(point[1])])
      : [[data.latitude, data.longitude]];
  } else if (!sameTrip) {
    history = [[data.latitude, data.longitude]];
  } else {
    history = rec.history;
    const last = history[history.length - 1];
    if (!last || Math.abs(last[0] - data.latitude) > 1e-6 || Math.abs(last[1] - data.longitude) > 1e-6) {
      history.push([data.latitude, data.longitude]);
    }
    if (history.length > 4000) history.splice(0, history.length - 4000);
  }
  rec.data = data;
  seenAt.set(data.vehicle_id, Date.now());
  rec.card.classList.remove("stale");
  applyHistory(rec, history);
  rec.marker.setLatLng([data.latitude, data.longitude]);
  aim(rec.marker, data.heading);
  if (rec.marker.isPopupOpen()) rec.marker.setPopupContent(popupHtml(data));
  renderCard(rec);
  document.getElementById("empty").hidden = fleet.size > 0;
  document.getElementById("count").textContent = String(fleet.size);
  scheduleFrame();
}

function applySnapshot(msg) {
  const incoming = new Set(msg.vehicles.map((vehicle) => vehicle.vehicle_id));
  for (const id of [...fleet.keys()]) {
    if (!incoming.has(id)) removeVehicle(id);
  }
  for (const vehicle of msg.vehicles) upsert(vehicle, true);
  document.getElementById("empty").hidden = fleet.size > 0;
  document.getElementById("count").textContent = String(fleet.size);
}

function beginAutoMove() {
  autoMoving = true;
  const end = () => { autoMoving = false; };
  map.once("moveend", end);
  setTimeout(end, 1200);
}

function frameVehicles() {
  const points = [...fleet.values()].map((rec) => [rec.data.latitude, rec.data.longitude]);
  beginAutoMove();
  if (points.length === 0) {
    map.setView(CENTER, 12);
    return;
  }
  if (points.length === 1) {
    map.setView(points[0], 14);
    return;
  }
  map.fitBounds(L.latLngBounds(points), { padding: [48, 48], maxZoom: 13 });
}

function scheduleFrame() {
  if (framed || userMoved || frameTimer) return;
  frameTimer = setTimeout(() => {
    frameTimer = null;
    frameVehicles();
    framed = true;
  }, 700);
}

function refreshStale() {
  const now = Date.now();
  for (const [id, at] of seenAt) {
    const rec = fleet.get(id);
    if (!rec) continue;
    const stale = now - at > 4000;
    if (rec.card.classList.contains("stale") !== stale) {
      rec.card.classList.toggle("stale", stale);
      renderCard(rec);
    }
  }
}

function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onopen = () => {
    retryMs = 400;
    setLink("live");
    ws.send(JSON.stringify({ role: "map" }));
  };
  ws.onmessage = (event) => {
    let msg;
    try {
      msg = JSON.parse(event.data);
    } catch {
      return;
    }
    noteMessage(msg);
    if (msg.type === "snapshot") applySnapshot(msg);
    else if (msg.type === "update") upsert(msg, false);
  };
  ws.onerror = () => ws.close();
  ws.onclose = () => {
    setLink("down");
    setTimeout(connect, retryMs);
    retryMs = Math.min(retryMs * 1.6, 4000);
  };
}

setLink("wait");
connect();
setInterval(refreshStale, 1000);
setTimeout(() => map.invalidateSize(), 0);
