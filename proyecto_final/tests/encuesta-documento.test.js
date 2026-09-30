import assert from "node:assert/strict";
import { test } from "node:test";
import { historialConsentimientoPublico } from "../src/utilidades/encuesta-documento.js";

test("el historial de consentimiento no expone empleado_id aunque venga en la fila", () => {
  const out = historialConsentimientoPublico([
    {
      seudonimo_id: "SEUD-2026-014892",
      empleado_id: "EMP-00142",
      version_consentimiento_id: "CONSENT-v3-2026-07-01",
      fecha_aceptacion: "2026-07-01",
      fecha_revocacion: null,
      estado: "ACEPTADO",
      ip_origen: "10.20.4.18",
    },
  ]);
  assert.deepEqual(Object.keys(out[0]).sort(), [
    "estado",
    "fecha_aceptacion",
    "fecha_revocacion",
    "seudonimo_id",
    "version_consentimiento_id",
  ]);
  assert.equal("empleado_id" in out[0], false);
  assert.equal("ip_origen" in out[0], false);
});
