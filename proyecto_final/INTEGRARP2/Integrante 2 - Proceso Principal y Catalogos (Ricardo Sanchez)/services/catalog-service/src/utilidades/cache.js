import crypto from "node:crypto";

/**
 * Gestión de caché Redis para catalog-service.
 * Claves: cache:catalogos:{recurso}:{hash}
 * Invalidación: cache:catalogos:{recurso}:*
 */

let redisCliente = null;

export function setRedisCliente(cliente) {
  redisCliente = cliente;
}

export function getRedisCliente() {
  return redisCliente;
}

export function generarHash(params = {}) {
  const clavesOrdenadas = Object.keys(params).sort();
  const objOrdenado = {};
  for (const k of clavesOrdenadas) {
    if (params[k] !== undefined && params[k] !== null) {
      objOrdenado[k] = params[k];
    }
  }
  return crypto
    .createHash("sha256")
    .update(JSON.stringify(objOrdenado))
    .digest("hex")
    .slice(0, 16);
}

export function construirClaveCache(recurso, params = {}) {
  const hash = generarHash(params);
  return `cache:catalogos:${recurso}:${hash}`;
}

export async function leerCache(clave) {
  try {
    if (!redisCliente || (redisCliente.status !== "ready" && redisCliente.status !== "connect")) {
      return null;
    }
    const raw = await redisCliente.get(clave);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export async function guardarCache(clave, valor, ttlSec = 300) {
  try {
    if (!redisCliente || (redisCliente.status !== "ready" && redisCliente.status !== "connect")) {
      return;
    }
    await redisCliente.set(clave, JSON.stringify(valor), "EX", ttlSec);
  } catch {
    // Degradación suave
  }
}

export async function invalidarCacheRecurso(recurso) {
  try {
    if (!redisCliente || (redisCliente.status !== "ready" && redisCliente.status !== "connect")) {
      return 0;
    }
    const patron = `cache:catalogos:${recurso}:*`;
    const claves = await redisCliente.keys(patron);
    if (claves && claves.length > 0) {
      await redisCliente.del(...claves);
      return claves.length;
    }
    return 0;
  } catch {
    return 0;
  }
}

export async function invalidarTodoCatalogo() {
  try {
    if (!redisCliente || (redisCliente.status !== "ready" && redisCliente.status !== "connect")) {
      return 0;
    }
    const patron = "cache:catalogos:*";
    const claves = await redisCliente.keys(patron);
    if (claves && claves.length > 0) {
      await redisCliente.del(...claves);
      return claves.length;
    }
    return 0;
  } catch {
    return 0;
  }
}
