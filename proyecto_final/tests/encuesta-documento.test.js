import assert from "node:assert/strict";
import { test } from "node:test";
import {
  documentoRespuestaMongo,
  historialConsentimientoPublico,
} from "../src/utilidades/encuesta-documento.js";

test("el documento Mongo no incluye empleado_id ni datos de identidad real", () => {
  const doc = documentoRespuestaMongo({
    seudonimo_id: "SEUD-2026-014892",
    instrumento_id: "INST-NOM035-GUIA3",
    version_instrumento: 2,
    campania_id: "CAMP-2026-Q3-CALLCENTER",
    unidad_organizacional_id: "UO-CALLCENTER-TURNO-B",
    version_consentimiento: "CONSENT-v3-2026-07-01",
    respuestas: [{ reactivo_id: "R-01", valor: 3 }],
  });
  assert.equal("empleado_id" in doc, false);
  assert.equal("nombre" in doc, false);
  assert.equal("correo" in doc, false);
  assert.equal(doc.version_consentimiento, "CONSENT-v3-2026-07-01");
  assert.equal(doc.version_instrumento, 2);
  assert.deepEqual(doc.respuestas, [{ reactivo_id: "R-01", valor: 3 }]);
});

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
