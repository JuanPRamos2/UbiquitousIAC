import test from "node:test";
import assert from "node:assert/strict";

import { aXml } from "@bienestar/comun/xmlizar.js";
import { ErrorApi } from "@bienestar/comun/errores.js";
import { actualizarEstadoSolicitud, crearSolicitud } from "../src/servicio.js";

test("support-service: serializacion XML genera estructura compatible con XSD", () => {
  const solicitud = {
    id: "SOL-ABC123DEF456",
    seudonimo_id: "SEUD-00001",
    mensaje: "Requiero orientacion sobre manejo de estres",
    fecha: "2026-04-10T10:00:00.000Z",
    estado: "ABIERTA",
    fecha_actualizacion: null,
    historial: [
      { estado: "ABIERTA", fecha: "2026-04-10T10:00:00.000Z", actor_id: null, nota: "Solicitud creada" },
    ],
  };
  const xml = aXml(solicitud, "solicitud_apoyo");
  assert.ok(xml.includes("<solicitud_apoyo"));
  assert.ok(xml.includes("<id>SOL-ABC123DEF456</id>"));
  assert.ok(xml.includes("<seudonimo_id>SEUD-00001</seudonimo_id>"));
  assert.ok(xml.includes("<estado>ABIERTA</estado>"));
  assert.ok(xml.includes("<historial>"));
  assert.ok(xml.includes("<entrada>"));
});

test("support-service: valida longitud minima del mensaje (minimo 8 caracteres)", async () => {
  await assert.rejects(
    async () => {
      await crearSolicitud({ actor: { sub: "USR-01" }, mensaje: "ayuda" });
    },
    (err) => err instanceof ErrorApi && err.http === 400
  );
});

test("support-service: rechaza transiciones no permitidas en solicitudes", async () => {
  const colMock = {
    findOneAndUpdate: async () => null,
    findOne: async () => ({
      id_publico: "SOL-001",
      estado: "CERRADA",
    }),
  };

  await assert.rejects(
    async () => {
      await actualizarEstadoSolicitud({
        id: "SOL-001",
        estado: "ABIERTA",
        actor: { sub: "ESP-01", perfil: "ESPECIALISTA" },
        colSoporte: colMock,
      });
    },
    (err) => err instanceof ErrorApi && err.codigo === "TRANSICION_NO_PERMITIDA" && err.http === 409
  );
});
