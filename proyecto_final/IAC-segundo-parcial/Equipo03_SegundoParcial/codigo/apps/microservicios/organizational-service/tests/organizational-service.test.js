import test from "node:test";
import assert from "node:assert/strict";

import { aXml } from "@bienestar/comun/xmlizar.js";
import { ErrorApi } from "@bienestar/comun/errores.js";
import { crearUnidad, eliminarUnidadLogica } from "../src/servicio.js";

test("organizational-service: serializacion XML genera estructura compatible con XSD", () => {
  const arbol = {
    unidad_raiz_id: "UNID-00001",
    total_nodos: 1,
    nodos: [
      {
        unidad_id: "UNID-00001",
        nombre: "Direccion General",
        tipo: "DIRECCION",
        nivel: 1,
        plantilla_declarada: 25,
        activa: true,
      },
    ],
  };
  const xml = aXml(arbol, "arbol_organizacional_respuesta");
  assert.ok(xml.includes("<arbol_organizacional_respuesta"));
  assert.ok(xml.includes("<unidad_raiz_id>UNID-00001</unidad_raiz_id>"));
  assert.ok(xml.includes("<nodos>"));
  assert.ok(xml.includes("<nodo>"));
  assert.ok(xml.includes("<plantilla_declarada>25</plantilla_declarada>"));
});

test("organizational-service: exige plantilla declarada >= 5 para evitar inferencia", async () => {
  await assert.rejects(
    async () => {
      await crearUnidad({
        nombre: "Micro Departamento",
        plantilla_declarada: 3, // Menor que 5
      });
    },
    (err) => err instanceof ErrorApi && err.http === 400
  );
});

test("organizational-service: permite creacion cuando plantilla >= 5", async () => {
  const dbPgMock = async (sql, params) => {
    return {
      unidad_id: params[0],
      nombre: params[1],
      plantilla_declarada: params[6],
      activa: params[7],
    };
  };

  const res = await crearUnidad({
    nombre: "Departamento Legal",
    plantilla_declarada: 8,
    dbPg: dbPgMock,
  });

  assert.equal(res.nombre, "Departamento Legal");
  assert.equal(res.plantilla_declarada, 8);
});

test("organizational-service: rechaza baja si tiene dependencias activas", async () => {
  // Mock que reporta 2 hijas activas
  const dbPgMock = async (sql) => {
    if (sql.includes("COUNT(*)")) return [{ total: 2 }];
    return [];
  };

  await assert.rejects(
    async () => {
      await eliminarUnidadLogica("UNID-PADRE", { dbPg: dbPgMock });
    },
    (err) => err instanceof ErrorApi && err.codigo === "DEPENDENCIAS_ACTIVAS" && err.http === 409
  );
});
