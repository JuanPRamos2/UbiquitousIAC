import { claveCache, claveContador, claveContadorDiario, claveLockCache } from "./claves-redis.js";
import { hashEstable } from "./paginacion.js";

function esperar(ms) {
  return new Promise((resolver) => setTimeout(resolver, ms));
}

export function crearCache({ redis, cfg, log }) {
  return {
    clave(recurso, partes) {
      const hash = hashEstable(partes);
      return {
        hash,
        clave: claveCache(cfg.serviceName, recurso, hash),
        lock: claveLockCache(cfg.serviceName, recurso, hash),
      };
    },
    async obtener(recurso, partes, calcular) {
      const { clave, lock } = this.clave(recurso, partes);
      try {
        const hit = await redis.get(clave);
        if (hit) {
          log.info("CACHE HIT", { clave });
          return { valor: JSON.parse(hit), cache: "HIT", clave };
        }
      } catch (err) {
        log.error("Redis no disponible al leer caché", { clave, error: err.message });
        return { valor: await calcular(), cache: "BYPASS", clave };
      }

      log.info("CACHE MISS", { clave });
      let bloqueado = false;
      try {
        const ok = await redis.set(lock, "1", "EX", cfg.lockTtl, "NX");
        bloqueado = ok === "OK";
        if (!bloqueado) {
          log.info("Lock de caché ocupado; se espera el resultado", { lock });
          for (let i = 0; i < 5; i += 1) {
            await esperar(80);
            const otra = await redis.get(clave);
            if (otra) {
              log.info("CACHE HIT", { clave, despues_de_espera: true });
              return { valor: JSON.parse(otra), cache: "HIT", clave };
            }
          }
        }
      } catch (err) {
        log.warn("No se pudo adquirir el lock de caché", { lock, error: err.message });
      }

      try {
        const valor = await calcular();
        try {
          await redis.set(clave, JSON.stringify(valor), "EX", cfg.cacheTtl);
        } catch (err) {
          log.error("No se pudo guardar la caché", { clave, error: err.message });
        }
        return { valor, cache: "MISS", clave };
      } finally {
        if (bloqueado) await redis.del(lock).catch(() => {});
      }
    },
  };
}

export function crearContador({ redis, log, operacion, ttlDiario = 172800 }) {
  const total = claveContador(operacion);
  return {
    claveTotal: total,
    async incrementar() {
      const dia = new Date().toISOString().slice(0, 10);
      const diario = claveContadorDiario(operacion, dia);
      try {
        await redis.incr(total);
        const n = await redis.incr(diario);
        if (n === 1) await redis.expire(diario, ttlDiario);
      } catch (err) {
        log.warn("No se pudo incrementar el contador", { error: err.message, contador: operacion });
      }
    },
    async leer() {
      try {
        const valor = await redis.get(total);
        const ttl = await redis.ttl(total);
        return { clave: total, valor: Number(valor || 0), ttl };
      } catch (err) {
        log.warn("No se pudo leer el contador", { error: err.message, contador: operacion });
        return { clave: total, valor: null, ttl: null };
      }
    },
  };
}
