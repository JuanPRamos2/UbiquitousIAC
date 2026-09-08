import assert from "node:assert/strict";
import { test } from "node:test";
import { api } from "../src/rutas/index.js";

function rutasDe(router, prefix = "") {
  const out = [];
  for (const layer of router.stack || []) {
    if (layer.route) {
      const methods = Object.keys(layer.route.methods)
        .filter((m) => layer.route.methods[m])
        .map((m) => m.toUpperCase());
      out.push(`${methods.sort().join(",")} ${prefix}${layer.route.path}`);
    } else if (layer.name === "router" && layer.handle?.stack) {
      const match = String(layer.regexp || "");
      let next = prefix;
      if (match.includes("catalogos")) next = `${prefix}/catalogos`;
      else if (match.includes("encuestas")) next = `${prefix}/encuestas`;
      else if (match.includes("agregados")) next = `${prefix}/agregados`;
      else if (match.includes("auditoria")) next = `${prefix}/auditoria`;
      else if (match.includes("portal")) next = `${prefix}/portal`;
      else if (match.includes("auth")) next = `${prefix}/auth`;
      out.push(...rutasDe(layer.handle, next));
    }
  }
  return out;
}

test("las rutas que abre cada perfil existen fuera de /portal", () => {
  const rutas = rutasDe(api);
  for (const esperada of [
    "GET /catalogos/unidades",
    "GET /catalogos/campanias",
    "GET /catalogos/instrumentos",
    "GET /catalogos/cuentas",
    "GET /catalogos/versiones-consentimiento",
    "GET /encuestas/consentimiento",
    "POST /encuestas/consentimiento",
    "GET /encuestas/mias",
    "GET /encuestas/mis-accesos",
    "POST /encuestas/soporte",
    "GET /agregados/parametros/k",
    "GET /agregados/parametros",
    "PATCH /agregados/parametros",
    "GET /auditoria/soporte",
    "GET /auditoria/consentimientos",
    "GET /portal/escritorio",
  ]) {
    assert.equal(rutas.includes(esperada), true, `falta ${esperada} en ${rutas.join(" | ")}`);
  }
});
