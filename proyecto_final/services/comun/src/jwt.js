import jwt from "jsonwebtoken";
import { HttpError, esFalloDeDependencia } from "./errores.js";
import { claveContexto, claveRevocado, claveSesion } from "./claves-redis.js";
import { TODOS_LOS_PERFILES } from "./perfiles.js";

function prefijoJti(jti) {
  return String(jti || "").slice(0, 8);
}

async function contextoDe(usuarioId, redis, query, ttl) {
  const clave = claveContexto(usuarioId);
  try {
    const cacheado = await redis.get(clave);
    if (cacheado) return JSON.parse(cacheado);
  } catch {
    /* Si Redis falla aquí, la verificación de sesión ya habría fallado antes. */
  }
  const resultado = await query(
    `SELECT COALESCE(e.unidad_organizacional_id, up.unidad_alcance_id) AS unidad_organizacional_id
     FROM usuarios.usuario u
     LEFT JOIN usuarios.usuario_perfil up ON up.usuario_id = u.usuario_id
     LEFT JOIN usuarios.empleado e ON e.usuario_id = u.usuario_id AND e.activo = TRUE
     WHERE u.usuario_id = $1
     ORDER BY up.fecha_asignacion
     LIMIT 1`,
    [usuarioId]
  );
  const contexto = {
    unidad_organizacional_id: resultado.rows[0]?.unidad_organizacional_id || null,
  };
  try {
    await redis.set(clave, JSON.stringify(contexto), "EX", ttl);
  } catch {
    /* El contexto sigue siendo válido aunque no se pueda cachear. */
  }
  return contexto;
}

/**
 * ESTO SE DEBE CONECTAR CON AUTH SERVICE.
 * Hoy el monolito firma el JWT con JWT_SECRET (HS256) y escribe:
 *   session:{jti}  y  revoked:{jti}
 * Cuando exista auth-service basta con conservar ese contrato
 * o publicar JWT_PUBLIC_KEY / JWT_ISSUER / JWT_AUDIENCE.
 */
export function crearAutenticacion({ redis, query, cfg, log }) {
  return async function autenticar(req, _res, next) {
    try {
      const header = req.headers.authorization || "";
      const [esquema, token] = header.split(" ");
      if (!token || esquema !== "Bearer") {
        throw new HttpError(401, "SIN_TOKEN", "Falta el token Bearer");
      }
      const algoritmo = cfg.jwtAlgorithm || "HS256";
      const clave = algoritmo.startsWith("RS") ? cfg.jwtPublicKey : cfg.jwtSecret;
      if (!clave) throw new HttpError(500, "CONFIGURACION", "Falta la clave de verificación JWT");

      let payload;
      try {
        payload = jwt.verify(token, clave, {
          algorithms: [algoritmo],
          issuer: cfg.jwtIssuer || undefined,
          audience: cfg.jwtAudience || undefined,
        });
      } catch (err) {
        if (err.name === "TokenExpiredError") {
          throw new HttpError(401, "TOKEN_EXPIRADO", "El token expiró");
        }
        throw new HttpError(401, "TOKEN_INVALIDO", "Token inválido");
      }

      if (!payload.sub || !payload.perfil || !payload.jti) {
        throw new HttpError(401, "TOKEN_INVALIDO", "El token no trae los claims requeridos");
      }
      if (!TODOS_LOS_PERFILES.includes(payload.perfil)) {
        throw new HttpError(403, "RBAC", "El perfil del token no existe en Nexum");
      }

      let revocado = 0;
      let sesion = 0;
      try {
        revocado = await redis.exists(claveRevocado(payload.jti));
        if (cfg.requireSession) sesion = await redis.exists(claveSesion(payload.jti));
      } catch (err) {
        log.error("No se pudo consultar Redis durante la autenticación", {
          error: err.message,
          jti: prefijoJti(payload.jti),
        });
        throw new HttpError(503, "REDIS_NO_DISPONIBLE", "No se pudo verificar la sesión");
      }
      if (revocado) {
        throw new HttpError(401, "TOKEN_REVOCADO", "La sesión fue cerrada o el token fue revocado");
      }
      if (cfg.requireSession && !sesion) {
        throw new HttpError(401, "SESION_INVALIDA", "No hay una sesión vigente para este token");
      }

      const contexto = await contextoDe(payload.sub, redis, query, cfg.contextoTtl);
      req.actor = {
        usuario_id: payload.sub,
        perfil: payload.perfil,
        jti: payload.jti,
        exp: payload.exp,
        unidad_organizacional_id: contexto.unidad_organizacional_id,
      };
      log.info("Petición autenticada", {
        usuario_id: payload.sub,
        perfil: payload.perfil,
        jti: prefijoJti(payload.jti),
        path: req.path,
      });
      return next();
    } catch (err) {
      if (esFalloDeDependencia(err)) {
        return next(new HttpError(503, "DEPENDENCIA_NO_DISPONIBLE", "No se pudo validar la identidad"));
      }
      return next(err);
    }
  };
}
