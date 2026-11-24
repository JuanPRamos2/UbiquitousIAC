import assert from "node:assert/strict";
import { test } from "node:test";
import { sqlParticipacion } from "../src/sql/reportes.sql.js";
import { crearServicioReportes } from "../src/servicios/reportes.servicio.js";

test("la participación no mete el identificador de unidad en el SQL si no hay filtro", () => {
  const libre = sqlParticipacion(null);
  assert.equal(libre.params.length, 0);
  assert.equal(libre.text.includes("$1"), false);
  const acotada = sqlParticipacion("UO-CC-TURNO-B");
  assert.deepEqual(acotada.params, ["UO-CC-TURNO-B"]);
  assert.match(acotada.text, /unidad_organizacional_id = \$1/);
});

test("la tendencia suprime grupos bajo k y no publica el n exacto", async () => {
  const repo = {
    async umbralK() {
      return 5;
    },
    async participacion(unidad) {
      assert.equal(unidad, "UO-CC-TURNO-B");
      return [
        { campania_id: "CAMP-2026-S1", nombre: "Medicion semana 1", n: 2 },
        { campania_id: "CAMP-2026-S2", nombre: "Medicion semana 2", n: 8 },
      ];
    },
    async tendencia() {
      return [{ campania_id: "CAMP-2026-S2", valor_protegido: 3.4 }];
    },
  };
  const cache = {
    async obtener(_recurso, partes, calcular) {
      assert.equal(partes.unidad, "UO-CC-TURNO-B");
      return { valor: await calcular(), cache: "MISS", clave: "cache:reports:tendencia:1" };
    },
  };
  const contador = { async incrementar() {} };
  const servicio = crearServicioReportes({ repo, cache, contador });
  const lider = { perfil: "LIDER", usuario_id: "USR-00005", unidad_organizacional_id: "UO-CC-TURNO-B" };
  await assert.rejects(
    () => servicio.tendencia(lider, { unidad_organizacional_id: "UO-LOG-TURNO-A" }),
    (err) => err.status === 403
  );
  const resultado = await servicio.tendencia(lider, {});
  assert.deepEqual(resultado.data.series[0].data, [null, 1]);
  assert.deepEqual(resultado.data.series[1].data, [null, 3.4]);
  assert.equal(JSON.stringify(resultado.data).includes('"n"'), false);
  assert.equal(resultado.cache, "MISS");
});
