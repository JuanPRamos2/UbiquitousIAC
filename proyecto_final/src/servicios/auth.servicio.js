import jwt from "jsonwebtoken";
import { v4 as uuid } from "uuid";
import { env } from "../config/env.js";
import { redis } from "../config/redis.js";
import * as Usuario from "../modelos/Usuario.js";
import { registrarAsync } from "./auditoria.servicio.js";
import { HttpError } from "../utilidades/errores.js";
import { ACCIONES, RESULTADOS, RECURSOS } from "../utilidades/catalogos-auditoria.js";
import { payloadPublicoUsuario } from "../utilidades/privacidad.js";
import { claveSesion, claveRevocado, claveLoginFallido } from "../utilidades/redis-claves.js";

export async function login({ correo, contrasena, correlacionId }) {
  const usuario = await Usuario.buscarUsuarioPorCorreo(correo);
  if (!usuario) {
    await registrarAsync({
      actor_id: "DESCONOCIDO",
      actor_perfil: "N/A",
      accion: ACCIONES.LOGIN_FALLIDO,
      recurso: RECURSOS.USUARIO,
      resultado: RESULTADOS.RECHAZADO,
      correlacion_id: correlacionId,
    });
    throw new HttpError(401, "CREDENCIALES_INVALIDAS", "Correo o contraseña incorrectos");
  }

  const fallos = Number((await redis.get(claveLoginFallido(usuario.usuario_id))) || 0);
  if (fallos >= env.loginMaxIntentos) {
    await registrarAsync({
      actor_id: usuario.usuario_id,
      actor_perfil: usuario.perfil,
      accion: ACCIONES.LOGIN_FALLIDO,
      recurso: RECURSOS.USUARIO,
      resultado: RESULTADOS.RECHAZADO,
      correlacion_id: correlacionId,
    });
    throw new HttpError(423, "CUENTA_BLOQUEADA", "Demasiados intentos fallidos. Espera 15 minutos.");
  }

  const ok = await Usuario.verificarContrasena(usuario.usuario_id, contrasena);
  if (!ok) {
    const n = await redis.incr(claveLoginFallido(usuario.usuario_id));
    if (n === 1) await redis.expire(claveLoginFallido(usuario.usuario_id), env.jwtExpiresSec);
    await registrarAsync({
      actor_id: usuario.usuario_id,
      actor_perfil: usuario.perfil,
      accion: ACCIONES.LOGIN_FALLIDO,
      recurso: RECURSOS.USUARIO,
      resultado: RESULTADOS.RECHAZADO,
      correlacion_id: correlacionId,
    });
    throw new HttpError(401, "CREDENCIALES_INVALIDAS", "Correo o contraseña incorrectos");
  }

  await redis.del(claveLoginFallido(usuario.usuario_id));
  const jti = uuid();
  const token = jwt.sign(
    { sub: usuario.usuario_id, perfil: usuario.perfil, jti },
    env.jwtSecret,
    { expiresIn: env.jwtExpiresSec }
  );
  await redis.hset(claveSesion(jti), {
    usuario_id: usuario.usuario_id,
    perfil: usuario.perfil,
  });
  await redis.expire(claveSesion(jti), env.jwtExpiresSec);
  await Usuario.marcarUltimoAcceso(usuario.usuario_id);
  await registrarAsync({
    actor_id: usuario.usuario_id,
    actor_perfil: usuario.perfil,
    accion: ACCIONES.LOGIN_EXITOSO,
    recurso: RECURSOS.USUARIO,
    resultado: RESULTADOS.EXITO,
    correlacion_id: correlacionId,
  });

  const contexto = await Usuario.contextoOperativo(usuario.usuario_id);
  return {
    token,
    expira_en: env.jwtExpiresSec,
    ...payloadPublicoUsuario({
      usuario_id: usuario.usuario_id,
      perfil: usuario.perfil,
      seudonimo_id: contexto?.seudonimo_id,
    }),
    nombre: usuario.nombre || null,
    unidad_organizacional_id: contexto?.unidad_organizacional_id || null,
  };
}

export async function logout({ jti, exp, actor, correlacionId }) {
  const ttl = Math.max(1, exp - Math.floor(Date.now() / 1000));
  await redis.set(claveRevocado(jti), "1", "EX", ttl);
  await redis.del(claveSesion(jti));
  await registrarAsync({
    actor_id: actor.usuario_id,
    actor_perfil: actor.perfil,
    accion: ACCIONES.LOGOUT,
    recurso: RECURSOS.USUARIO,
    resultado: RESULTADOS.EXITO,
    correlacion_id: correlacionId,
  });
}

export async function sesionValida(jti) {
  if (await redis.exists(claveRevocado(jti))) return false;
  return (await redis.exists(claveSesion(jti))) === 1;
}

export async function sesionActual(usuario) {
  const perfil = await Usuario.perfilDeUsuario(usuario.usuario_id);
  const contexto = await Usuario.contextoOperativo(usuario.usuario_id);
  return {
    ...payloadPublicoUsuario({
      usuario_id: usuario.usuario_id,
      perfil: usuario.perfil,
      seudonimo_id: contexto?.seudonimo_id,
    }),
    nombre: perfil?.nombre || null,
    unidad_organizacional_id: contexto?.unidad_organizacional_id || null,
  };
}
