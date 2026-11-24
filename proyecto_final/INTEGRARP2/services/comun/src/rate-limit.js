import { HttpError } from "./errores.js";
import { claveRateLimit } from "./claves-redis.js";

export function crearRateLimit({ redis, cfg, log }) {
  return async function rateLimit(req, res, next) {
    const identidad = req.actor?.usuario_id || req.ip || "anonimo";
    const ventana = cfg.rateWindow;
    const limite = cfg.rateLimit;
    const bucket = Math.floor(Date.now() / 1000 / ventana);
    const clave = claveRateLimit(cfg.serviceName, identidad, bucket);
    try {
      const usados = await redis.incr(clave);
      const restanteTtl = await redis.ttl(clave);
      if (restanteTtl < 0) await redis.expire(clave, ventana);
      const ttl = restanteTtl > 0 ? restanteTtl : ventana;
      res.setHeader("X-RateLimit-Limit", String(limite));
      res.setHeader("X-RateLimit-Remaining", String(Math.max(0, limite - usados)));
      if (usados > limite) {
        res.setHeader("Retry-After", String(ttl));
        log.warn("Rate limit excedido", { identidad, clave, usados, limite });
        return next(
          new HttpError(429, "LIMITE_EXCEDIDO", "Demasiadas solicitudes. Intente más tarde.", {
            retry_after: ttl,
          })
        );
      }
      return next();
    } catch (err) {
      if (err instanceof HttpError) return next(err);
      log.error("Rate limit no pudo consultar Redis", { error: err.message });
      return next(new HttpError(503, "REDIS_NO_DISPONIBLE", "No se pudo aplicar el control de tráfico"));
    }
  };
}
