import jwt from "jsonwebtoken";
import { env } from "../config/env.js";
import { sesionValida } from "../servicios/auth.servicio.js";
import { HttpError } from "../utilidades/errores.js";

const PERFIL_POR_NOMBRE = {
  Colaborador: "COLABORADOR",
  "Lider de unidad": "LIDER",
  "Especialista de bienestar": "ESPECIALISTA",
  "Auditor de cumplimiento": "AUDITOR",
  "Administrador del sistema": "ADMINISTRADOR",
};

function perfilCodigo(valor) {
  if (!valor) return valor;
  return PERFIL_POR_NOMBRE[valor] || valor;
}

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
      perfil: perfilCodigo(payload.perfil),
      jti: payload.jti,
      exp: payload.exp,
      unidad_organizacional_id: payload.unidad_alcance || null,
    };
    next();
  } catch (err) {
    next(err);
  }
}
