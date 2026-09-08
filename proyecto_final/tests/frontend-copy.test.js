import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import path from "node:path";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const css = readFileSync(new URL("../web/css/estilos.css", import.meta.url), "utf8");
const js = readFileSync(new URL("../web/js/app.js", import.meta.url), "utf8");
const consentimiento = readFileSync(
  new URL("../src/servicios/consentimiento.servicio.js", import.meta.url),
  "utf8"
);
const encuestaRutas = readFileSync(new URL("../src/rutas/encuesta.rutas.js", import.meta.url), "utf8");
const catalogoRutas = readFileSync(new URL("../src/rutas/catalogo.rutas.js", import.meta.url), "utf8");
const root = path.dirname(fileURLToPath(new URL("../package.json", import.meta.url)));

test("el login del prototipo no expone motores ni JWT", () => {
  const prohibido = /PostgreSQL|MongoDB|Redis|pgcrypto|JWT|TTL/i;
  assert.equal(prohibido.test(html), false);
  assert.match(html, /Plataforma de Bienestar Laboral/);
  assert.match(html, /Nexum Servicios Corporativos/);
  assert.match(html, /Cerrar sesión/);
  assert.match(html, /Iniciar sesión/);
});

test("la paleta sigue el prototipo navy y teal", () => {
  assert.match(css, /--navy:\s*#1f3864/i);
  assert.match(css, /--teal:\s*#0f6b62/i);
  assert.match(css, /--serif:/);
});

test("el sitio público y los documentos de diseño están en la app", () => {
  assert.match(html, /id="publico"/);
  assert.match(html, /Tu bienestar, medido sin vigilarte/);
  assert.match(html, /docs\/prototipo_bienestar_nexum\.html/);
  assert.match(html, /docs\/wireframes_bienestar_nexum\.html/);
  assert.equal(existsSync(path.join(root, "web/docs/prototipo_bienestar_nexum.html")), true);
  assert.equal(existsSync(path.join(root, "web/docs/wireframes_bienestar_nexum.html")), true);
  assert.equal(existsSync(path.join(root, "web/vendor/highcharts.min.js")), true);
});

test("las secciones de cada perfil cargan catálogos y no dependen solo del portal", () => {
  assert.match(js, /\/catalogos\/campanias/);
  assert.match(js, /\/catalogos\/unidades/);
  assert.match(js, /\/catalogos\/instrumentos/);
  assert.match(js, /\/agregados\/parametros\/k/);
  assert.match(js, /async function cargarCampanias/);
  assert.match(js, /async function cargarUnidades/);
  assert.match(js, /async function cargarK/);
  assert.match(js, /function apiOpcional/);
  assert.match(js, /Resultado suprimido/);
});

test("el consentimiento propio y el historial de Ana no quedan en un helper inexistente", () => {
  assert.match(consentimiento, /historialConsentimientoPublico/);
  assert.match(consentimiento, /from "\.\.\/utilidades\/encuesta-documento\.js"/);
  assert.match(encuestaRutas, /\/consentimiento/);
  assert.match(encuestaRutas, /\/mias/);
  assert.match(encuestaRutas, /\/mis-accesos/);
  assert.match(catalogoRutas, /\/cuentas/);
  assert.match(catalogoRutas, /\/versiones-consentimiento/);
});
