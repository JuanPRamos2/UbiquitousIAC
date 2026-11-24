import test from "node:test";
import assert from "node:assert/strict";

import { entero, numero, booleano, texto, arreglo } from "../src/validacion.js";
import { traducirErrorPg } from "../src/pg-errores.js";
import { aXml } from "../src/xmlizar.js";
import { crearContratoOpenApi } from "../src/openapi.js";
import { ErrorApi } from "../src/errores.js";

test("validacion.entero parsea enteros y strings de enteros", () => {
  assert.equal(entero(10, "campo"), 10);
  assert.equal(entero("42", "campo"), 42);
  assert.equal(entero(null, "campo", { requerido: false, defecto: 5 }), 5);

  assert.throws(() => entero("no-numero", "campo"), (err) => err instanceof ErrorApi && err.http === 400);
  assert.throws(() => entero(3.14, "campo"), (err) => err instanceof ErrorApi && err.http === 400);
  assert.throws(() => entero(3, "campo", { min: 5 }), (err) => err instanceof ErrorApi && err.http === 400);
});

test("validacion.booleano parsea correctamente booleano y string booleano", () => {
  assert.equal(booleano(true, "campo"), true);
  assert.equal(booleano("true", "campo"), true);
  assert.equal(booleano(false, "campo"), false);
  assert.equal(booleano("false", "campo"), false);
  assert.equal(booleano(null, "campo", { defecto: true }), true);
  assert.throws(() => booleano("invalido", "campo"), (err) => err instanceof ErrorApi && err.http === 400);
});

test("validacion.texto y arreglo validan restricciones", () => {
  assert.equal(texto("  hola  ", "campo"), "hola");
  assert.throws(() => texto("", "campo", { requerido: true }), (err) => err instanceof ErrorApi && err.http === 400);
  assert.throws(() => texto("ab", "campo", { minLong: 3 }), (err) => err instanceof ErrorApi && err.http === 400);

  assert.deepEqual(arreglo(["a", "b"], "items"), ["a", "b"]);
  assert.deepEqual(arreglo("solo-uno", "items"), ["solo-uno"]);
  assert.throws(() => arreglo([], "items", { minElementos: 1 }), (err) => err instanceof ErrorApi && err.http === 400);
});

test("pg-errores mapea codigos de PostgreSQL", () => {
  const errDuplicado = traducirErrorPg({ code: "23505", detail: "llave duplicada" });
  assert.equal(errDuplicado.http, 409);
  assert.equal(errDuplicado.codigo, "RECURSO_DUPLICADO");

  const errFk = traducirErrorPg({ code: "23503", detail: "fk no existe" });
  assert.equal(errFk.http, 422);
  assert.equal(errFk.codigo, "REFERENCIA_INVALIDA");

  const errCheck = traducirErrorPg({ code: "23514", detail: "check fallo" });
  assert.equal(errCheck.http, 422);
  assert.equal(errCheck.codigo, "RESTRICCION_VIOLADA");

  const errPermiso = traducirErrorPg({ code: "42501" });
  assert.equal(errPermiso.http, 403);
  assert.equal(errPermiso.codigo, "PERMISO_DENEGADO");
});

test("xmlizar serializa listas con elementos singulares sincronizados", () => {
  const xml = aXml({ cuestionarios: [{ id: 1 }, { id: 2 }] }, "cuestionarios_respuesta");
  assert.ok(xml.includes("<cuestionarios>"));
  assert.ok(xml.includes("<cuestionario>"));
  assert.ok(xml.includes("</cuestionario>"));
  assert.ok(xml.includes("</cuestionarios>"));
});

test("crearContratoOpenApi genera estructura OpenAPI 3.0 con 7 respuestas comunes", () => {
  const contrato = crearContratoOpenApi({
    nombre: "Test Service",
    version: "1.0.0",
    descripcion: "Prueba de contrato",
    rutas: {},
  });
  assert.equal(contrato.openapi, "3.0.3");
  assert.equal(Object.keys(contrato.components.responses).length, 7);
  assert.ok(contrato.components.responses.SolicitudInvalida);
  assert.ok(contrato.components.responses.SinPermiso);
});
