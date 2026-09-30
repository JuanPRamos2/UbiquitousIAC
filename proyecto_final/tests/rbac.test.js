import assert from "node:assert/strict";
import { test } from "node:test";
import { PERFILES, RECURSOS, ACCIONES } from "../src/utilidades/catalogos-auditoria.js";

test("RBAC cubre los cinco perfiles de la base v2", () => {
  assert.deepEqual(Object.values(PERFILES).sort(), [
    "ADMINISTRADOR",
    "AUDITOR",
    "COLABORADOR",
    "ESPECIALISTA",
    "LIDER",
  ]);
});

test("login y el autoreporte usan códigos del catálogo de auditoría v2", () => {
  assert.equal(RECURSOS.USUARIO, "USUARIO");
  assert.equal(ACCIONES.LOGIN_EXITOSO, "LOGIN_EXITOSO");
  assert.equal(ACCIONES.AUTOREPORTE_ENVIADO, "AUTOREPORTE_ENVIADO");
  assert.equal(ACCIONES.AGREGADO_CONSULTADO, "AGREGADO_CONSULTADO");
});
