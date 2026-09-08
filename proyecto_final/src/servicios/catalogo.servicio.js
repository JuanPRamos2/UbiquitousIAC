import * as Catalogo from "../modelos/Catalogo.js";
import { PERFILES } from "../utilidades/catalogos-auditoria.js";
import { HttpError } from "../utilidades/errores.js";
import * as Usuario from "../modelos/Usuario.js";

export async function unidades(actor) {
  const rows = await Catalogo.listarUnidades();
  if (actor.perfil === PERFILES.ADMIN_SISTEMA || actor.perfil === PERFILES.AUDITOR) {
    return rows;
  }
  const ctx = await Usuario.contextoOperativo(actor.usuario_id);
  if (!ctx?.unidad_organizacional_id) {
    throw new HttpError(403, "SIN_UNIDAD", "El usuario no tiene unidad organizacional");
  }
  return rows.filter((u) => u.unidad_organizacional_id === ctx.unidad_organizacional_id);
}

export async function campanias(actor) {
  if (actor.perfil === PERFILES.ADMIN_SISTEMA || actor.perfil === PERFILES.AUDITOR) {
    return Catalogo.listarCampanias();
  }
  const ctx = await Usuario.contextoOperativo(actor.usuario_id);
  if (!ctx?.unidad_organizacional_id) return [];
  return Catalogo.listarCampaniasDeUnidad(ctx.unidad_organizacional_id);
}

export async function instrumentos() {
  return Catalogo.listarInstrumentos();
}

export async function versionesConsentimiento() {
  return Catalogo.listarVersionesConsentimiento();
}

export async function cuentas() {
  return {
    usuarios: await Usuario.listarCuentas(),
    perfiles: await Usuario.listarPerfiles(),
  };
}

export async function reactivos(instrumentoId, version) {
  return Catalogo.reactivosDeVersion(instrumentoId, Number(version));
}
