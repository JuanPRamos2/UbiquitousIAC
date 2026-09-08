import * as Catalogo from "../modelos/Catalogo.js";
import * as Usuario from "../modelos/Usuario.js";
import * as Soporte from "../modelos/Soporte.js";
import * as Catalogos from "./catalogo.servicio.js";
import * as Consentimiento from "./consentimiento.servicio.js";
import * as Encuesta from "./encuesta.servicio.js";
import { registrarAsync } from "./auditoria.servicio.js";
import { HttpError } from "../utilidades/errores.js";
import { ACCIONES, RESULTADOS, RECURSOS, PERFILES } from "../utilidades/catalogos-auditoria.js";
import { invalidarTodosLosCachesAgregado } from "./cache-agregado.js";

async function seguro(fn, fallback) {
  try {
    return await fn();
  } catch (err) {
    console.error(err.message);
    return fallback;
  }
}

export async function escritorio(actor) {
  const ctx = await seguro(() => Usuario.contextoOperativo(actor.usuario_id), null);
  const out = {
    perfil: actor.perfil,
    unidad_organizacional_id: ctx?.unidad_organizacional_id || null,
    unidades: await seguro(() => Catalogos.unidades(actor), []),
    campanias: await seguro(() => Catalogos.campanias(actor), []),
    instrumentos: [],
    k: 5,
    parametros: {},
  };
  if (actor.perfil === PERFILES.ADMIN_SISTEMA || actor.perfil === PERFILES.AUDITOR) {
    out.instrumentos = await seguro(() => Catalogos.instrumentos(), []);
  }
  if (actor.perfil !== PERFILES.COLAB) {
    out.k = await seguro(() => Catalogo.leerUmbralK(), 5);
    out.parametros = await seguro(() => Catalogo.leerParametros(), {});
  }
  return out;
}

export async function miConsentimiento(actor) {
  return Consentimiento.mio(actor);
}

export async function cambiarMiConsentimiento({ actor, aceptar, correlacionId }) {
  return Consentimiento.cambiarMio({ actor, aceptar, correlacionId });
}

export async function misEvaluaciones(actor) {
  return Encuesta.mias(actor);
}

export async function solicitarApoyo({ actor, mensaje, correlacionId }) {
  const texto = String(mensaje || "").trim();
  if (texto.length < 8) {
    throw new HttpError(400, "PAYLOAD_INVALIDO", "Escriba una solicitud con más detalle");
  }
  const ctx = await Usuario.contextoOperativo(actor.usuario_id);
  if (!ctx?.seudonimo_id) {
    throw new HttpError(403, "SIN_SEUDONIMO", "Su cuenta no tiene participación operativa");
  }
  const out = await Soporte.crearSolicitud({ seudonimo_id: ctx.seudonimo_id, mensaje: texto.slice(0, 1000) });
  return { ok: true, fecha: out.fecha };
}

export async function listarApoyo() {
  const rows = await Soporte.listarSolicitudes();
  return {
    data: rows.map((r) => ({
      fecha: r.fecha,
      mensaje: r.mensaje,
      estado: r.estado || "ABIERTA",
    })),
  };
}

export async function cuentas() {
  return {
    usuarios: await Usuario.listarCuentas(),
    perfiles: await Usuario.listarPerfiles(),
  };
}

export async function configuracion() {
  const parametros = await Catalogo.leerParametros();
  return {
    k: Number(parametros.k || 5),
    version_activa_consentimiento: parametros.version_activa_consentimiento || null,
    versiones: await Catalogo.listarVersionesConsentimiento(),
  };
}

export async function guardarConfiguracion({ actor, k, version_activa_consentimiento, correlacionId }) {
  if (k !== undefined && k !== null && k !== "") {
    const valor = Number(k);
    if (!Number.isInteger(valor) || valor < 2 || valor > 50) {
      throw new HttpError(400, "K_INVALIDO", "k debe ser un entero entre 2 y 50");
    }
    await Catalogo.actualizarUmbralK(valor, actor.usuario_id);
    await invalidarTodosLosCachesAgregado();
    await registrarAsync({
      actor_id: actor.usuario_id,
      actor_perfil: actor.perfil,
      accion: ACCIONES.CAMBIO_UMBRAL_K,
      recurso: RECURSOS.PARAMETRO_GLOBAL,
      resultado: RESULTADOS.EXITO,
      correlacion_id: correlacionId,
    });
  }
  if (version_activa_consentimiento) {
    await Catalogo.actualizarParametro(
      "version_activa_consentimiento",
      version_activa_consentimiento,
      actor.usuario_id
    );
    await registrarAsync({
      actor_id: actor.usuario_id,
      actor_perfil: actor.perfil,
      accion: ACCIONES.CAMBIO_CONSENTIMIENTO,
      recurso: RECURSOS.VERSION_CONSENTIMIENTO,
      resultado: RESULTADOS.EXITO,
      correlacion_id: correlacionId,
    });
  }
  return configuracion();
}
