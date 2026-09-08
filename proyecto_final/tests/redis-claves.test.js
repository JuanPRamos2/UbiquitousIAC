import assert from "node:assert/strict";
import { test } from "node:test";
import {
  claveSesion,
  claveRevocado,
  claveLoginFallido,
  claveCacheAgregado,
  claveLockAgregado,
} from "../src/utilidades/redis-claves.js";

test("las claves Redis siguen el contrato del diseño políglota", () => {
  assert.equal(claveSesion("abc"), "session:abc");
  assert.equal(claveRevocado("abc"), "revoked:abc");
  assert.equal(claveLoginFallido("USR-00001"), "contador:login_fallido:USR-00001");
  assert.equal(
    claveCacheAgregado("UO-CALLCENTER-TURNO-B", "CAMP-2026-Q3-CALLCENTER"),
    "cache:agregado:UO-CALLCENTER-TURNO-B:CAMP-2026-Q3-CALLCENTER"
  );
  assert.equal(claveLockAgregado("UO-CALLCENTER-TURNO-B"), "lock:calculo_agregado:UO-CALLCENTER-TURNO-B");
});
