/**
 * Cache de lectura en Redis para los catalogos.
 *
 * Los catalogos se leen en cada pantalla y cambian pocas veces al mes: es
 * el caso en que una cache paga. La invalidacion es explicita en cada
 * escritura (invalidar) y no por expiracion sola, porque una unidad
 * renombrada debe aparecer renombrada en la siguiente pantalla, no cinco
 * minutos despues.
 *
 * Si Redis no responde, se consulta la base y se sigue: la cache acelera,
 * no es la fuente de verdad.
 */
import { cacheTtlSeg } from "./entorno.js";
import { obtenerRedis } from "./redis.js";

const PREFIJO = "cache:catalogo:";

export function claveDe(recurso, parametros = {}) {
  const partes = Object.keys(parametros).sort()
    .filter((k) => parametros[k] !== undefined && parametros[k] !== null && parametros[k] !== "")
    .map((k) => `${k}=${parametros[k]}`);
  return `${PREFIJO}${recurso}${partes.length ? `?${partes.join("&")}` : ""}`;
}

export async function leer(clave) {
  try {
    const crudo = await obtenerRedis().get(clave);
    return crudo ? JSON.parse(crudo) : null;
  } catch { return null; }
}

export async function guardar(clave, valor, ttl = cacheTtlSeg) {
  try {
    await obtenerRedis().set(clave, JSON.stringify(valor), "EX", ttl);
  } catch { /* cache caida: no es un error de la peticion */ }
}

/** Borra todas las entradas de un recurso. Se llama en cada escritura. */
export async function invalidar(recurso) {
  try {
    const r = obtenerRedis();
    const patron = `${PREFIJO}${recurso}*`;
    let cursor = "0";
    do {
      const [siguiente, claves] = await r.scan(cursor, "MATCH", patron, "COUNT", 500);
      cursor = siguiente;
      if (claves.length) await r.del(...claves);
    } while (cursor !== "0");
  } catch { /* idem */ }
}

/** Envuelve una lectura: devuelve de cache o consulta y guarda. */
export async function conCache(recurso, parametros, consultaFn) {
  const clave = claveDe(recurso, parametros);
  const enCache = await leer(clave);
  if (enCache) return { ...enCache, _cache: true };
  const datos = await consultaFn();
  await guardar(clave, datos);
  return { ...datos, _cache: false };
}
