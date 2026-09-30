import { redis } from "../config/redis.js";
import { env } from "../config/env.js";
import * as Catalogo from "../modelos/Catalogo.js";
import * as Usuario from "../modelos/Usuario.js";
import { registrarAsync } from "./auditoria.servicio.js";
import { invalidarTodosLosCachesAgregado } from "./cache-agregado.js";
import { HttpError } from "../utilidades/errores.js";
import { ACCIONES, RESULTADOS, RECURSOS, PERFILES } from "../utilidades/catalogos-auditoria.js";
import { claveCacheAgregado, claveLockAgregado } from "../utilidades/redis-claves.js";

function resultadoAuditoria(estado) {
  if (estado === "PUBLICADO") return RESULTADOS.EXITO;
  if (estado === "PRESUPUESTO_PRIVACIDAD_AGOTADO") return RESULTADOS.PRESUPUESTO_AGOTADO;
  return RESULTADOS.GRUPO_INSUFICIENTE;
}

function accionAuditoria(estado) {
  if (estado === "PRESUPUESTO_PRIVACIDAD_AGOTADO") return ACCIONES.PRESUPUESTO_AGOTADO;
  if (estado === "GRUPO_INSUFICIENTE") return ACCIONES.GRUPO_INSUFICIENTE;
  return ACCIONES.AGREGADO_CONSULTADO;
}

async function esperarCache(cacheKey) {
  for (let i = 0; i < 5; i += 1) {
    await new Promise((r) => setTimeout(r, 200));
    const again = await redis.get(cacheKey);
    if (again) return JSON.parse(again);
  }
  return null;
}

export async function consultarAgregado({ actor, unidadId, campaniaId, correlacionId }) {
  if (actor.perfil === PERFILES.COLABORADOR) {
    throw new HttpError(403, "RBAC", "El colaborador no consulta agregados");
  }
  if (actor.perfil === PERFILES.LIDER) {
    const ctx = await Usuario.contextoOperativo(actor.usuario_id);
    if (ctx?.unidad_organizacional_id !== unidadId) {
      throw new HttpError(403, "RBAC", "Solo puedes ver agregados de tu unidad");
    }
  }

  const cacheKey = claveCacheAgregado(unidadId, campaniaId);
  const cached = await redis.get(cacheKey);
  if (cached) {
    const parsed = JSON.parse(cached);
    await registrarAsync({
      actor_id: actor.usuario_id,
      actor_perfil: actor.perfil,
      accion: accionAuditoria(parsed.motivo || (parsed.visible ? "PUBLICADO" : "GRUPO_INSUFICIENTE")),
      recurso: RECURSOS.UNIDAD,
      recurso_id: unidadId,
      resultado: resultadoAuditoria(parsed.motivo || (parsed.visible ? "PUBLICADO" : "GRUPO_INSUFICIENTE")),
      correlacion_id: correlacionId,
    });
    return parsed;
  }

  let lock = await redis.set(
    claveLockAgregado(unidadId),
    actor.usuario_id,
    "EX",
    env.redisTtl.lockAgregadoSec,
    "NX"
  );
  if (!lock) {
    const fromWait = await esperarCache(cacheKey);
    if (fromWait) {
      await registrarAsync({
        actor_id: actor.usuario_id,
        actor_perfil: actor.perfil,
      accion: accionAuditoria(fromWait.motivo || (fromWait.visible ? "PUBLICADO" : "GRUPO_INSUFICIENTE")),
      recurso: RECURSOS.UNIDAD,
      recurso_id: unidadId,
      resultado: resultadoAuditoria(fromWait.motivo || (fromWait.visible ? "PUBLICADO" : "GRUPO_INSUFICIENTE")),
        correlacion_id: correlacionId,
      });
      return fromWait;
    }
    lock = await redis.set(
      claveLockAgregado(unidadId),
      actor.usuario_id,
      "EX",
      env.redisTtl.lockAgregadoSec,
      "NX"
    );
  }

  try {
    const campania = await Catalogo.obtenerCampania(campaniaId);
    if (!campania) throw new HttpError(404, "CAMPANIA_INVALIDA", "Campaña no encontrada");

    const k = await Catalogo.leerUmbralK();
    const global = await Catalogo.calcularAgregadoProtegido({
      campaniaId,
      unidadId,
      dimensionId: null,
      actorId: actor.usuario_id,
    });
    if (!global || global.estado === "CAMPANIA_INVALIDA") {
      throw new HttpError(404, "CAMPANIA_INVALIDA", "Campaña no encontrada");
    }

    const detalle = {};
    if (global.estado === "PUBLICADO") {
      const dimensiones = await Catalogo.listarDimensiones();
      for (const dimension of dimensiones) {
        const fila = await Catalogo.calcularAgregadoProtegido({
          campaniaId,
          unidadId,
          dimensionId: dimension.dimension_id,
          actorId: actor.usuario_id,
        });
        if (fila?.estado === "PUBLICADO" && fila.valor_protegido != null) {
          detalle[dimension.nombre] = Number(fila.valor_protegido);
        }
      }
    }

    const publico = {
      visible: global.estado === "PUBLICADO",
      motivo: global.estado === "PUBLICADO" ? undefined : global.estado,
      k,
      promedio_global: global.valor_protegido == null ? null : Number(global.valor_protegido),
      detalle,
      epsilon: global.epsilon == null ? null : Number(global.epsilon),
      mensaje: global.mensaje || null,
    };

    await redis.set(cacheKey, JSON.stringify(publico), "EX", env.redisTtl.cacheAgregadoSec);
    await registrarAsync({
      actor_id: actor.usuario_id,
      actor_perfil: actor.perfil,
      accion: accionAuditoria(global.estado),
      recurso: RECURSOS.UNIDAD,
      recurso_id: unidadId,
      resultado: resultadoAuditoria(global.estado),
      correlacion_id: correlacionId,
    });
    return publico;
  } finally {
    if (lock) await redis.del(claveLockAgregado(unidadId));
  }
}

export async function leerK() {
  const k = await Catalogo.leerUmbralK();
  return { k };
}

export async function leerParametros() {
  const parametros = await Catalogo.leerParametros();
  return {
    k: Number(parametros.k || 5),
    version_activa_consentimiento: parametros.version_activa_consentimiento || null,
  };
}

export async function guardarParametros({ actor, k, version_activa_consentimiento, correlacionId }) {
  if (k !== undefined && k !== null && k !== "") {
    await cambiarK({ actor, k, correlacionId });
  }
  if (version_activa_consentimiento) {
    await Catalogo.activarAviso(version_activa_consentimiento);
    await registrarAsync({
      actor_id: actor.usuario_id,
      actor_perfil: actor.perfil,
      accion: ACCIONES.PARAMETRO_MODIFICADO,
      recurso: RECURSOS.AVISO,
      recurso_id: version_activa_consentimiento,
      resultado: RESULTADOS.EXITO,
      correlacion_id: correlacionId,
    });
  }
  return leerParametros();
}

export async function cambiarK({ actor, k, correlacionId }) {
  const valor = Number(k);
  if (!Number.isInteger(valor) || valor < 2 || valor > 50) {
    throw new HttpError(400, "K_INVALIDO", "k debe ser un entero entre 2 y 50");
  }
  await Catalogo.actualizarUmbralK(valor, actor.usuario_id);
  await invalidarTodosLosCachesAgregado();
  await registrarAsync({
    actor_id: actor.usuario_id,
    actor_perfil: actor.perfil,
    accion: ACCIONES.PARAMETRO_MODIFICADO,
    recurso: RECURSOS.PARAMETRO,
    recurso_id: "k_umbral_minimo",
    resultado: RESULTADOS.EXITO,
    correlacion_id: correlacionId,
  });
  return { k: valor };
}
