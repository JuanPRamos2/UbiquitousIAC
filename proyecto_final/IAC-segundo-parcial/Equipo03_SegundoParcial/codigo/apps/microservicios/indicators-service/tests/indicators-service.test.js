import test from "node:test";
import assert from "node:assert/strict";

import { aXml } from "@bienestar/comun/xmlizar.js";
import { ErrorApi } from "@bienestar/comun/errores.js";
import { consultarAgregados, clasificarRiesgo } from "../src/servicio.js";

test("indicators-service: serializacion XML genera estructura compatible con XSD", () => {
  const datos = {
    campania_id: "CAMP-2026-01",
    unidad_id: "UNID-00001",
    indicadores: [
      {
        clave: "IND_ESTRES",
        nombre: "Estres",
        dimension_id: "DIM-01",
        valor: 3.2,
        n_observaciones: 15,
        k_umbral: 5,
        suprimido_por_umbral: false,
        nivel_riesgo: "MEDIO",
        precision: "PRECISION_SUFICIENTE",
      },
    ],
    total: 1,
    fuente: "postgresql_protegido",
  };
  const xml = aXml(datos, "agregados_respuesta");
  assert.ok(xml.includes("<agregados_respuesta"));
  assert.ok(xml.includes("<indicadores>"));
  assert.ok(xml.includes("<indicador>"));
  assert.ok(xml.includes("<clave>IND_ESTRES</clave>"));
  assert.ok(xml.includes("<valor>3.2</valor>"));
  assert.ok(xml.includes("<suprimido_por_umbral>false</suprimido_por_umbral>"));
});

test("indicators-service: umbral k >= 5 suprime valor si n < 5", async () => {
  // Mock PG returning row with n = 3 (< 5)
  const mockPg = async () => [
    {
      dimension_id: "DIM-01",
      dimension_nombre: "Estres",
      estado_publicacion: "GRUPO_INSUFICIENTE",
      n_observaciones: 3,
      k_aplicado: 5,
      valor_protegido: 4.1,
      precision_advertencia: "PRECISION_LIMITADA",
    },
  ];

  const res = await consultarAgregados({
    campania_id: "CAMP-2026-01",
    unidad_id: "UNID-00002",
    actor: { perfil: "ADMINISTRADOR" },
    dbPg: mockPg,
  });

  assert.equal(res.indicadores.length, 1);
  const ind = res.indicadores[0];
  assert.equal(ind.suprimido_por_umbral, true);
  assert.equal(ind.valor, null);
  assert.equal(ind.nivel_riesgo, "NO_EVALUABLE");
});

test("indicators-service: permite valor si n >= 5", async () => {
  const mockPg = async () => [
    {
      dimension_id: "DIM-01",
      dimension_nombre: "Estres",
      estado_publicacion: "PUBLICADO",
      n_observaciones: 18,
      k_aplicado: 5,
      valor_protegido: 2.1,
      precision_advertencia: "PRECISION_SUFICIENTE",
    },
  ];

  const res = await consultarAgregados({
    campania_id: "CAMP-2026-01",
    unidad_id: "UNID-00001",
    actor: { perfil: "ADMINISTRADOR" },
    dbPg: mockPg,
  });

  assert.equal(res.indicadores.length, 1);
  const ind = res.indicadores[0];
  assert.equal(ind.suprimido_por_umbral, false);
  assert.equal(ind.valor, 2.1);
  assert.equal(ind.nivel_riesgo, "BAJO");
});

test("indicators-service: clasificacion de riesgo correcta", () => {
  assert.equal(clasificarRiesgo(null), "NO_EVALUABLE");
  assert.equal(clasificarRiesgo(1.8), "BAJO");
  assert.equal(clasificarRiesgo(3.0), "MEDIO");
  assert.equal(clasificarRiesgo(4.2), "ALTO");
});
