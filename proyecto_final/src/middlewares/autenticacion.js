import jwt from "jsonwebtoken";
import { env } from "../config/env.js";
import { sesionValida } from "../servicios/auth.servicio.js";
import { HttpError } from "../utilidades/errores.js";

export async function autenticar(req, _res, next) {
  try {
    const header = req.headers.authorization || "";
    const [, token] = header.split(" ");
    if (!token) throw new HttpError(401, "SIN_TOKEN", "Falta el token Bearer");
    let payload;
    try {
      payload = jwt.verify(token, env.jwtSecret);
    } catch {
      throw new HttpError(401, "TOKEN_INVALIDO", "Token inválido o expirado");
    }
    const vigente = await sesionValida(payload.jti);
    if (!vigente) {
      throw new HttpError(401, "TOKEN_REVOCADO", "La sesión fue cerrada o ya no existe");
    }
    req.actor = {
      usuario_id: payload.sub,
      perfil: payload.perfil,
      jti: payload.jti,
      exp: payload.exp,
    };
    next();
  } catch (err) {
    next(err);
  }
}
