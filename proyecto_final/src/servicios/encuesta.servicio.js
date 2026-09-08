import * as Catalogo from "../modelos/Catalogo.js";
import * as Encuesta from "../modelos/Encuesta.js";
import * as Usuario from "../modelos/Usuario.js";
import * as Bitacora from "../modelos/Bitacora.js";
import { registrarAsync } from "./auditoria.servicio.js";
import { invalidarCacheAgregado } from "./cache-agregado.js";
import { HttpError } from "../utilidades/errores.js";
import { ACCIONES, RESULTADOS, RECURSOS, PERFILES } from "../utilidades/catalogos-auditoria.js";
import { documentoRespuestaMongo } from "../utilidades/encuesta-documento.js";

export async function guardarAutoreporte({ actor, body, correlacionId }) {
  const { seudonimo_id, campania_id, respuestas } = body || {};
  if (!seudonimo_id || !campania_id || !Array.isArray(respuestas)) {
    throw new HttpError(400, "PAYLOAD_INVALIDO", "seudonimo_id, campania_id y respuestas son obligatorios");
  }

  const seudonimo = await Catalogo.obtenerSeudonimo(seudonimo_id);
  if (!seudonimo || !seudonimo.activo) {
    throw new HttpError(400, "SEUDONIMO_INVALIDO", "El seudónimo no existe o no está activo");
  }

  if (actor.perfil === PERFILES.COLAB && seudonimo.usuario_id !== actor.usuario_id) {
    throw new HttpError(403, "SEUDONIMO_AJENO", "No puedes reportar con un seudónimo que no te corresponde");
  }

  const campania = await Catalogo.obtenerCampania(campania_id);
  if (!campania || !campania.activa) {
    throw new HttpError(400, "CAMPANIA_INVALIDA", "La campaña no existe o no está activa");
  }

  const asignada = await Catalogo.campaniaAsignadaAUnidad(
    campania_id,
    seudonimo.unidad_organizacional_id
  );
  if (!asignada) {
    throw new HttpError(400, "CAMPANIA_NO_ASIGNADA", "La campaña no está asignada a la unidad del seudónimo");
  }

  const consentimiento = await Catalogo.consentimientoVigente(seudonimo_id);
  if (!consentimiento) {
    throw new HttpError(403, "SIN_CONSENTIMIENTO", "No hay consentimiento vigente para este seudónimo");
  }

  if (await Encuesta.existeRespuesta(seudonimo_id, campania_id)) {
    throw new HttpError(409, "YA_RESPONDIO", "Este seudónimo ya respondió la campaña (RN-01)");
  }

  const plantilla = await Catalogo.reactivosDeVersion(
    campania.instrumento_id,
    campania.version_instrumento
  );
  const porId = new Map(plantilla.map((r) => [r.reactivo_id, r]));
  const arreglo = [];
  for (const item of respuestas) {
    const def = porId.get(item.reactivo_id);
    if (!def) {
      throw new HttpError(400, "REACTIVO_DESCONOCIDO", `Reactivo no pertenece al instrumento: ${item.reactivo_id}`);
    }
    const valor = Number(item.valor);
    if (!Number.isInteger(valor) || valor < def.escala_min || valor > def.escala_max) {
      throw new HttpError(400, "VALOR_FUERA_DE_ESCALA", `Valor inválido para ${item.reactivo_id}`);
    }
    arreglo.push({ reactivo_id: item.reactivo_id, valor });
  }
  for (const def of plantilla) {
    if (def.obligatorio && !arreglo.some((x) => x.reactivo_id === def.reactivo_id)) {
      throw new HttpError(400, "REACTIVO_FALTANTE", `Falta el reactivo obligatorio ${def.reactivo_id}`);
    }
  }

  const doc = documentoRespuestaMongo({
    seudonimo_id,
    instrumento_id: campania.instrumento_id,
    version_instrumento: campania.version_instrumento,
    campania_id,
    unidad_organizacional_id: seudonimo.unidad_organizacional_id,
    version_consentimiento: consentimiento.version_consentimiento_id,
    respuestas: arreglo,
  });

  const guardado = await Encuesta.insertarRespuesta(doc);
  await invalidarCacheAgregado(seudonimo.unidad_organizacional_id, campania_id);

  registrarAsync({
    actor_id: actor.usuario_id,
    actor_perfil: actor.perfil,
    accion: ACCIONES.CREACION_RESPUESTA,
    recurso: RECURSOS.RESPUESTA_ENCUESTA,
    resultado: RESULTADOS.EXITO,
    correlacion_id: correlacionId,
  });

  return {
    id: String(guardado._id),
    campania_id,
    instrumento_id: doc.instrumento_id,
    version_instrumento: doc.version_instrumento,
    version_consentimiento: doc.version_consentimiento,
    fecha_respuesta: doc.fecha_respuesta,
  };
}

export async function mias(actor) {
  const ctx = await Usuario.contextoOperativo(actor.usuario_id);
  if (!ctx?.seudonimo_id) {
    throw new HttpError(403, "SIN_SEUDONIMO", "El colaborador no tiene seudónimo operativo");
  }
  const docs = await Encuesta.respuestasDeSeudonimo(ctx.seudonimo_id);
  return {
    data: docs.map((d) => {
      const valores = (d.respuestas || []).map((x) => x.valor);
      const n = valores.length;
      return {
        campania_id: d.campania_id,
        fecha_respuesta: d.fecha_respuesta,
        promedio: n ? Number((valores.reduce((a, b) => a + b, 0) / n).toFixed(2)) : null,
      };
    }),
  };
}

export async function misAccesos(actor) {
  const rows = await Bitacora.listarBitacoraDeActor(actor.usuario_id);
  return {
    data: rows.map((row) => ({
      actor_id: row.actor_id,
      actor_perfil: row.actor_perfil,
      accion: row.accion,
      recurso: row.recurso,
      resultado: row.resultado,
      correlacion_id: row.correlacion_id,
      timestamp: row.timestamp,
    })),
  };
}

export async function estadoRespuesta({ actor, campaniaId }) {
  if (!campaniaId) {
    throw new HttpError(400, "PAYLOAD_INVALIDO", "campania_id es obligatorio");
  }
  const ctx = await Usuario.contextoOperativo(actor.usuario_id);
  if (!ctx?.seudonimo_id) {
    throw new HttpError(403, "SIN_SEUDONIMO", "El colaborador no tiene seudónimo operativo");
  }
  try {
    const ya = await Encuesta.existeRespuesta(ctx.seudonimo_id, campaniaId);
    return { campania_id: campaniaId, ya_respondio: ya };
  } catch (err) {
    console.error("estadoRespuesta", err.message);
    return { campania_id: campaniaId, ya_respondio: false };
  }
}
