import * as Catalogo from "../modelos/Catalogo.js";
import * as Usuario from "../modelos/Usuario.js";
import { registrarAsync } from "./auditoria.servicio.js";
import { HttpError } from "../utilidades/errores.js";
import { ACCIONES, RESULTADOS, RECURSOS } from "../utilidades/catalogos-auditoria.js";
import { historialConsentimientoPublico } from "../utilidades/encuesta-documento.js";

export async function historialPorSeudonimo({ actor, seudonimoId, correlacionId }) {
  if (!seudonimoId) {
    throw new HttpError(400, "PAYLOAD_INVALIDO", "seudonimo_id es obligatorio");
  }
  const existe = await Catalogo.existeSeudonimo(seudonimoId);
  if (!existe) {
    throw new HttpError(404, "SEUDONIMO_INVALIDO", "El seudónimo no existe");
  }

  const filas = await Catalogo.historialConsentimiento(seudonimoId);
  await registrarAsync({
    actor_id: actor.usuario_id,
    actor_perfil: actor.perfil,
    accion: ACCIONES.CONSULTA_HISTORIAL_CONSENTIMIENTO,
    recurso: RECURSOS.VERSION_CONSENTIMIENTO,
    resultado: RESULTADOS.EXITO,
    correlacion_id: correlacionId,
  });

  return { seudonimo_id: seudonimoId, data: historialConsentimientoPublico(filas) };
}

export async function mio(actor) {
  const ctx = await Usuario.contextoOperativo(actor.usuario_id);
  if (!ctx?.seudonimo_id) {
    throw new HttpError(403, "SIN_SEUDONIMO", "Su cuenta no tiene participación operativa");
  }
  const vigente = await Catalogo.consentimientoVigente(ctx.seudonimo_id);
  const historial = historialConsentimientoPublico(
    await Catalogo.historialConsentimiento(ctx.seudonimo_id)
  );
  const versionActiva = (await Catalogo.leerParametros()).version_activa_consentimiento || null;
  return {
    participando: Boolean(vigente),
    version_vigente: vigente?.version_consentimiento_id || null,
    version_activa: versionActiva,
    historial,
  };
}

export async function cambiarMio({ actor, aceptar, correlacionId }) {
  const ctx = await Usuario.contextoOperativo(actor.usuario_id);
  if (!ctx?.seudonimo_id) {
    throw new HttpError(403, "SIN_SEUDONIMO", "Su cuenta no tiene participación operativa");
  }
  if (aceptar) {
    const version =
      (await Catalogo.leerParametros()).version_activa_consentimiento ||
      (await Catalogo.listarVersionesConsentimiento())[0]?.version_consentimiento_id;
    if (!version) throw new HttpError(400, "PAYLOAD_INVALIDO", "No hay aviso de privacidad activo");
    await Catalogo.aceptarConsentimiento(ctx.seudonimo_id, version);
  } else {
    await Catalogo.revocarConsentimientosVigentes(ctx.seudonimo_id);
  }
  await registrarAsync({
    actor_id: actor.usuario_id,
    actor_perfil: actor.perfil,
    accion: ACCIONES.CAMBIO_CONSENTIMIENTO,
    recurso: RECURSOS.VERSION_CONSENTIMIENTO,
    resultado: RESULTADOS.EXITO,
    correlacion_id: correlacionId,
  });
  return mio(actor);
}

export async function listarEvidencia() {
  const filas = await Catalogo.listarConsentimientos();
  return { data: historialConsentimientoPublico(filas) };
}
