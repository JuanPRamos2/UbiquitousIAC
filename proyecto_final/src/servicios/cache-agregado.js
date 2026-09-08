import { redis } from "../config/redis.js";
import {
  claveCacheAgregado,
  PATRON_CACHE_AGREGADO,
} from "../utilidades/redis-claves.js";

export async function invalidarCacheAgregado(unidadId, campaniaId) {
  await redis.del(claveCacheAgregado(unidadId, campaniaId));
}

export async function invalidarTodosLosCachesAgregado() {
  const claves = [];
  let cursor = "0";
  do {
    const [siguiente, lote] = await redis.scan(cursor, "MATCH", PATRON_CACHE_AGREGADO, "COUNT", 100);
    cursor = siguiente;
    claves.push(...lote);
  } while (cursor !== "0");
  if (claves.length) await redis.del(...claves);
}
