import assert from "node:assert/strict";
import { test } from "node:test";
import { publicarAgregado, payloadPublicoUsuario } from "../src/utilidades/privacidad.js";

test("bajo el umbral k no se publican totales ni promedios", () => {
  const out = publicarAgregado({
    total: 3,
    k: 5,
    promedioGlobal: 4.2,
    detalle: { "R-01": 4, "SEUD-OCULTO": 1 },
  });
  assert.equal(out.visible, false);
  assert.equal(out.motivo, "GRUPO_INSUFICIENTE");
  assert.equal("total_respuestas" in out, false);
  assert.equal("promedio_global" in out, false);
  assert.equal("detalle" in out, false);
});

test("al superar k se publican métricas sin identidad", () => {
  const out = publicarAgregado({
    total: 8,
    k: 5,
    promedioGlobal: 3.4,
    detalle: { "R-01": 3.1 },
  });
  assert.equal(out.visible, true);
  assert.equal(out.total_respuestas, 8);
  assert.equal(out.promedio_global, 3.4);
  assert.deepEqual(out.detalle, { "R-01": 3.1 });
});

test("el payload de usuario no incluye empleado_id ni nombre", () => {
  const out = payloadPublicoUsuario({
    usuario_id: "USR-00001",
    perfil: "COLAB",
    seudonimo_id: "SEUD-2026-014892",
    empleado_id: "EMP-00142",
    nombre: "Ana",
  });
  assert.deepEqual(Object.keys(out).sort(), ["perfil", "seudonimo_id", "usuario_id"]);
  assert.equal("empleado_id" in out, false);
  assert.equal("nombre" in out, false);
});
