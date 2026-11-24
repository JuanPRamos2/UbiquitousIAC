import test from "node:test";
import assert from "node:assert/strict";

import { aXml } from "@bienestar/comun/xmlizar.js";
import { ErrorApi } from "@bienestar/comun/errores.js";
import { registrarRespuestas, guardarBorrador, obtenerBorrador } from "../src/servicio.js";

test("survey-service: serializacion XML genera estructura compatible con XSD", () => {
  const datos = {
    cuestionarios: [
      { cuestionario_id: "CUEST-01", nombre: "Clima", activo: true },
      { cuestionario_id: "CUEST-02", nombre: "Estres", activo: false },
    ],
    total: 2,
  };
  const xml = aXml(datos, "cuestionarios_respuesta");
  assert.ok(xml.includes("<cuestionarios_respuesta"));
  assert.ok(xml.includes("<cuestionarios>"));
  assert.ok(xml.includes("<cuestionario>"));
  assert.ok(xml.includes("<cuestionario_id>CUEST-01</cuestionario_id>"));
  assert.ok(xml.includes("<total>2</total>"));
});

test("survey-service: regla D-01 rechaza presencia de empleado_id en respuestas", async () => {
  const peticionConEmpleado = {
    cuestionario_id: "CUEST-01",
    campania_id: "CAMP-2026-01",
    seudonimo_id: "SEUD-00001",
    respuestas: [{ reactivo_id: "R-01", valor: 4, empleado_id: "EMP-999" }],
  };

  await assert.rejects(
    async () => {
      await registrarRespuestas(peticionConEmpleado);
    },
    (err) => err instanceof ErrorApi && err.codigo === "CAMPO_PROHIBIDO" && err.http === 422
  );
});

test("survey-service: previene respuestas duplicadas para misma campania y seudonimo", async () => {
  const dbMock = {
    collection: () => ({
      findOne: async () => ({ _id: "previa", seudonimo_id: "SEUD-00001" }),
    }),
  };

  await assert.rejects(
    async () => {
      await registrarRespuestas({
        cuestionario_id: "CUEST-01",
        campania_id: "CAMP-2026-01",
        seudonimo_id: "SEUD-00001",
        respuestas: [{ reactivo_id: "R-01", valor: 5 }],
        dbMongo: dbMock,
      });
    },
    (err) => err instanceof ErrorApi && err.codigo === "ENCUESTA_YA_RESPONDIDA" && err.http === 409
  );
});

test("survey-service: borradores se guardan y recuperan correctamente", async () => {
  let guardado = null;
  const dbMock = {
    collection: () => ({
      updateOne: async (_filtro, actualizacion) => {
        guardado = actualizacion.$set;
      },
      findOne: async () => guardado,
    }),
  };

  const resGuarda = await guardarBorrador({
    cuestionario_id: "CUEST-01",
    seudonimo_id: "SEUD-00001",
    campania_id: "CAMP-2026-01",
    respuestas: [{ reactivo_id: "R-01", valor: 3 }],
    dbMongo: dbMock,
  });
  assert.equal(resGuarda.cuestionario_id, "CUEST-01");
  assert.equal(resGuarda.respuestas.length, 1);

  const resObtiene = await obtenerBorrador({
    cuestionario_id: "CUEST-01",
    seudonimo_id: "SEUD-00001",
    dbMongo: dbMock,
  });
  assert.equal(resObtiene.cuestionario_id, "CUEST-01");
  assert.equal(resObtiene.seudonimo_id, "SEUD-00001");
});
