import assert from "node:assert/strict";
import { test } from "node:test";
import { PERFILES, RECURSOS, ACCIONES } from "../src/utilidades/catalogos-auditoria.js";

test("RBAC cubre los cuatro perfiles del esquema", () => {
  assert.deepEqual(Object.values(PERFILES).sort(), [
    "ADMIN_SISTEMA",
    "AUDITOR",
    "COLAB",
    "LIDER_TURNO",
  ]);
});

test("login y logout usan el recurso USUARIO del catálogo de auditoría", () => {
  assert.equal(RECURSOS.USUARIO, "USUARIO");
  assert.equal(ACCIONES.LOGIN_EXITOSO, "LOGIN_EXITOSO");
  assert.equal(ACCIONES.CONSULTA_HISTORIAL_CONSENTIMIENTO, "CONSULTA_HISTORIAL_CONSENTIMIENTO");
});
