import test from "node:test";
import assert from "node:assert/strict";
import { generarXml, solicitaXml } from "../src/utilidades/serializador.js";
import { registrarRespuesta } from "../src/servicios/proceso-encuesta.servicio.js";
import { crearSolicitud, actualizarEstado } from "../src/servicios/solicitud-apoyo.servicio.js";

test("main-process-service: serialización XML con caracteres escapados", () => {
  const data = {
    mensaje: "Orientación de salud & bienestar",
    estado: "EN_PROCESO",
    total: 3,
  };
  const xml = generarXml(data, "solicitud_apoyo");
  assert.match(xml, /<\?xml version="1.0" encoding="UTF-8"\?>/);
  assert.match(xml, /<solicitud_apoyo[\s>]/);
  assert.match(xml, /xmlns="http:\/\/nexum\.com\.mx\/bienestar\/v1"/);
  assert.match(xml, /<mensaje>Orientación de salud &amp; bienestar<\/mensaje>/);
  assert.match(xml, /<estado>EN_PROCESO<\/estado>/);
});

test("main-process-service: negociación de contenido detecta XML por query o header", () => {
  assert.equal(solicitaXml({ query: { format: "xml" } }), true);
  assert.equal(solicitaXml({ query: { format: "json" } }), false);
  assert.equal(solicitaXml({ headers: { accept: "application/xml" } }), true);
});

test("main-process-service: regla D-01 rechaza presencia de empleado_id en respuestas", async () => {
  await assert.rejects(
    async () => {
      await registrarRespuesta({
        actor: { usuario_id: "USR-001", perfil: "COLAB" },
        cuerpo: {
          empleado_id: 100,
          campania_id: 1,
          respuestas: [],
        },
        correlacionId: "corr-123",
      });
    },
    {
      name: "ErrorApi",
      message: /No se admite 'empleado_id'/,
    }
  );
});

test("main-process-service: validación de tamaño mínimo en mensaje de solicitud", async () => {
  await assert.rejects(
    async () => {
      await crearSolicitud({
        actor: { usuario_id: "USR-001", perfil: "COLAB" },
        mensaje: "hola", // Menor a 8 caracteres
        correlacionId: "corr-123",
      });
    },
    {
      name: "ErrorApi",
      message: /Escribe la solicitud con mas detalle/,
    }
  );
});

test("main-process-service: rechaza transiciones a estados inválidos en solicitudes", async () => {
  await assert.rejects(
    async () => {
      await actualizarEstado({
        id: "670c5e1234567890abcdef12",
        estado: "ESTADO_INVENTADO",
        actor: { usuario_id: "USR-001" },
        correlacionId: "corr-123",
      });
    },
    {
      name: "ErrorApi",
      message: /Estado 'ESTADO_INVENTADO' no valido/,
    }
  );
});
