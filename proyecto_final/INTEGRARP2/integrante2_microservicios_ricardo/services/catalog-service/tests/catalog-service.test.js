import test from "node:test";
import assert from "node:assert/strict";
import { generarXml, solicitaXml } from "../src/utilidades/serializador.js";
import { mapearErrorPg } from "../src/utilidades/pg-errores.js";

test("catalog-service: serialización XML con caracteres escapados", () => {
  const data = {
    nombre: "Unidad & Calidad <Especial>",
    activa: true,
    total: 10,
  };
  const xml = generarXml(data, "unidad");
  assert.match(xml, /<\?xml version="1.0" encoding="UTF-8"\?>/);
  assert.match(xml, /<unidad[\s>]/);
  assert.match(xml, /xmlns="http:\/\/nexum\.com\.mx\/bienestar\/v1"/);
  assert.match(xml, /<nombre>Unidad &amp; Calidad &lt;Especial&gt;<\/nombre>/);
  assert.match(xml, /<activa>true<\/activa>/);
  assert.match(xml, /<total>10<\/total>/);
});

test("catalog-service: negociación de contenido detecta XML por query o header", () => {
  assert.equal(solicitaXml({ query: { format: "xml" } }), true);
  assert.equal(solicitaXml({ query: { format: "json" } }), false);
  assert.equal(solicitaXml({ headers: { accept: "application/xml" } }), true);
  assert.equal(solicitaXml({ headers: { accept: "application/json" } }), false);
});

test("catalog-service: mapeo de errores de PostgreSQL a códigos HTTP correctos", () => {
  const errDuplicado = { code: "23505", message: "unique violation" };
  const httpErr = mapearErrorPg(errDuplicado);
  assert.equal(httpErr.status, 409);
  assert.equal(httpErr.code, "CONFLICTO_DUPLICADO");

  const errFk = { code: "23503", message: "foreign key violation" };
  const httpErrFk = mapearErrorPg(errFk);
  assert.equal(httpErrFk.status, 422);
  assert.equal(httpErrFk.code, "ERROR_REFERENCIA");

  const errCheck = { code: "23514", message: "check violation" };
  const httpErrCheck = mapearErrorPg(errCheck);
  assert.equal(httpErrCheck.status, 422);
  assert.equal(httpErrCheck.code, "REGLA_INTEGRIDAD");
});
