/**
 * Autenticacion JWT compartida con el sistema web y con auth-service.
 *
 * El secreto y la instancia de Redis son los mismos para los ocho
 * microservicios. Las consecuencias son las que se quieren:
 *   - un token emitido por auth-service sirve en catalog-service;
 *   - un cierre de sesion en cualquier componente revoca en todos, porque
 *     la lista de revocados vive en Redis y no en la memoria de un proceso.
 *
 * Un JWT con firma valida NO basta: se consulta Redis en cada peticion.
 * Si Redis no responde se rechaza con 503, igual que en los servicios en
 * Python. En el sistema web la decision fue la contraria (degradar y
 * seguir) porque ahi ya hay una sesion establecida y negar todo dejaria el
 * portal inservible; aqui se atiende a clientes externos y ante la duda no
 * se abre.
 */
import jsonwebtoken from "jsonwebtoken";

import { jwt as cfgJwt } from "./entorno.js";
import { ErrorApi } from "./errores.js";
import { obtenerRedis } from "./redis.js";

export function leerToken(req) {
  const cabecera = req.headers?.authorization || "";
  if (cabecera.startsWith("Bearer ")) return cabecera.slice(7).trim();
  // Se acepta tambien la cookie del sistema web, para que el navegador
  // pueda llamar a los microservicios sin duplicar el token.
  const cookies = req.headers?.cookie || "";
  const m = cookies.match(/(?:^|;\s*)bienestar_sesion=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export function decodificar(token) {
  if (!cfgJwt.secreto) {
    throw new ErrorApi("CONFIGURACION", "Falta JWT_SECRETO en este ambiente", 500);
  }
  try {
    return jsonwebtoken.verify(token, cfgJwt.secreto, { algorithms: [cfgJwt.algoritmo] });
  } catch (e) {
    if (e?.name === "TokenExpiredError") {
      throw new ErrorApi("TOKEN_EXPIRADO", "El token expiro. Renueva la sesion.", 401);
    }
    throw new ErrorApi("TOKEN_INVALIDO", "El token no es valido.", 401);
  }
}

export async function sesionViva(jti) {
  const r = obtenerRedis();
  if (await r.exists(`revocado:${jti}`)) return false;
  return Boolean(await r.exists(`sesion:${jti}`));
}

/** Middleware: valida firma, vigencia y sesion. Deja la identidad en req.actor. */
export async function autenticar(req, res, next) {
  try {
    const token = leerToken(req);
    if (!token) {
      throw new ErrorApi("TOKEN_AUSENTE",
        "Falta el encabezado Authorization: Bearer <token>.", 401);
    }
    const carga = decodificar(token);
    let viva;
    try {
      viva = await sesionViva(carga.jti || "");
    } catch {
      throw new ErrorApi("DEPENDENCIA_NO_DISPONIBLE",
        "No se pudo verificar la sesion.", 503);
    }
    if (!viva) {
      throw new ErrorApi("SESION_REVOCADA", "La sesion fue cerrada o revocada.", 401);
    }
    req.actor = carga;
    next();
  } catch (e) {
    next(e);
  }
}
