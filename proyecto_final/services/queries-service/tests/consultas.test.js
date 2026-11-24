import assert from "node:assert/strict";
import { test } from "node:test";
import { HttpError } from "../../comun/src/errores.js";
import { sqlCampanias } from "../src/sql/consultas.sql.js";
import { crearServicioConsultas } from "../src/servicios/consultas.servicio.js";
import { filtrosAuditoria, filtrosCampania } from "../src/validacion.js";

test("los filtros rechazan parámetros incorrectos y un rango invertido", () => {
  assert.throws(() => filtrosCampania({ page: "0" }), (err) => err instanceof HttpError && err.status === 400);
  assert.throws(() => filtrosCampania({ estado: "OTRO" }), (err) => err.status === 400);
  assert.throws(() => filtrosCampania({ sort: "nombre;drop" }), (err) => err.status === 400);
  assert.throws(
    () => filtrosAuditoria({ desde: "2026-09-02", hasta: "2026-08-01" }),
    (err) => err.status === 422
  );
  const ok = filtrosCampania({ search: "semana", estado: "ABIERTA", page: "1", limit: "10" });
  assert.equal(ok.estado, "ABIERTA");
  assert.equal(ok.offset, 0);
});

test("la consulta de campañas parametriza el texto y no lo concatena", () => {
  const sql = sqlCampanias({
    search: "a' OR 1=1",
    estado: "ABIERTA",
    limit: 20,
    offset: 0,
    columna: "c.nombre",
    order: "ASC",
  });
  assert.equal(sql.text.includes("OR 1=1"), false);
  assert.equal(sql.params.includes("ABIERTA"), true);
  assert.ok(sql.params.some((param) => String(param).includes("OR 1=1")));
  assert.match(sql.text, /ILIKE \$2 ESCAPE/);
});

test("el servicio devuelve 404 y el líder no lee otra unidad", async () => {
  const cache = {
    async obtener(_recurso, _partes, calcular) {
      const valor = await calcular();
      return { valor, cache: "MISS", clave: "cache:queries:test:1" };
    },
  };
  const contador = { async incrementar() {}, async leer() { return { clave: "counter:queries:consultas", valor: 0, ttl: -1 }; } };
  const repo = {
    async campaniaPorId() {
      return null;
    },
    async intervencionPorId() {
      return { intervencion_id: "9", unidad_organizacional_id: "UO-LOG-TURNO-A" };
    },
  };
  const servicio = crearServicioConsultas({ repo, cache, contador });
  await assert.rejects(
    () => servicio.campania({ perfil: "ESPECIALISTA", usuario_id: "USR-00003" }, "CAMP-NO-EXISTE"),
    (err) => err.status === 404
  );
  await assert.rejects(
    () => servicio.intervencion(
      { perfil: "LIDER", usuario_id: "USR-00005", unidad_organizacional_id: "UO-CC-TURNO-B" },
      "9"
    ),
    (err) => err.status === 403
  );
});
