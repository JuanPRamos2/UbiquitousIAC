/**
 * Solicitudes de apoyo: alta, listado y cambio de estado.
 *
 * El seudonimo se resuelve en la base a partir del usuario de la sesion y
 * nunca se acepta del cliente: aceptarlo permitiria pedir apoyo en nombre
 * de otra persona, o peor, descubrir el seudonimo de alguien probando
 * valores.
 */
import { ErrorApi } from "@bienestar/comun/errores.js";
import { registrarEventoProceso } from "@bienestar/comun/modelos/EventosProceso.js";
import * as Soporte from "@bienestar/comun/modelos/Soporte.js";
import { contextoOperativo } from "@bienestar/comun/modelos/Usuario.js";

const MIN_MENSAJE = 8;
const MAX_MENSAJE = 1000;

export async function crearSolicitud({ actor, mensaje, correlacionId, colSoporte, colEventos, ctxUsuario }) {
  const texto = String(mensaje || "").trim();
  if (texto.length < MIN_MENSAJE) {
    throw new ErrorApi("PARAMETRO_INVALIDO",
      `Escribe la solicitud con mas detalle: al menos ${MIN_MENSAJE} caracteres.`, 400);
  }

  const ctx = ctxUsuario || (await contextoOperativo(actor?.sub || actor?.usuario_id));
  if (!ctx?.seudonimo_id) {
    throw new ErrorApi("SIN_SEUDONIMO",
      "La cuenta no tiene participacion operativa en el programa.", 403);
  }

  const doc = await Soporte.crearSolicitud({
    seudonimo_id: ctx.seudonimo_id,
    mensaje: texto.slice(0, MAX_MENSAJE),
    correlacion_id: correlacionId,
  }, colSoporte);

  let eventoId = null;
  try {
    const evento = await registrarEventoProceso({
      seudonimo_id: ctx.seudonimo_id,
      correlacion_id: correlacionId,
      tipo: "SOLICITUD_CREADA",
      detalle: { solicitud_id: doc.id },
    }, colEventos);
    eventoId = evento.id;
  } catch { /* trazabilidad degradada */ }

  return {
    id: doc.id,
    seudonimo_id: doc.seudonimo_id,
    mensaje: doc.mensaje,
    fecha: doc.fecha,
    estado: doc.estado,
    fecha_actualizacion: doc.fecha_actualizacion || null,
    historial: doc.historial,
    evento_id: eventoId,
  };
}

export async function actualizarEstado({ id, estado, nota, actor, correlacionId, colSoporte, colEventos }) {
  if (!id) {
    throw new ErrorApi("PARAMETRO_FALTANTE",
      "El identificador de la solicitud es obligatorio.", 400);
  }
  if (!Soporte.ESTADOS_SOLICITUD.includes(estado)) {
    throw new ErrorApi("ESTADO_INVALIDO",
      `Estado '${estado}' no valido. Permitidos: ${Soporte.ESTADOS_SOLICITUD.join(", ")}.`, 400);
  }

  const actualizado = await Soporte.actualizarEstadoSolicitud({
    id, estado, actor_id: actor?.sub || actor?.usuario_id, nota: nota ? String(nota).trim() : undefined,
  }, colSoporte);

  if (!actualizado) {
    // Puede ser que la solicitud no exista, o que exista y la transicion
    // no este permitida. Se distinguen porque son dos problemas distintos
    // para quien llama: uno se arregla con otro identificador y el otro no
    // se arregla.
    const existente = await Soporte.obtenerSolicitud(id, colSoporte);
    if (!existente) {
      throw new ErrorApi("SOLICITUD_NO_ENCONTRADA",
        `No existe la solicitud '${id}'.`, 404);
    }
    throw new ErrorApi("TRANSICION_NO_PERMITIDA",
      `Una solicitud en estado ${existente.estado} no puede pasar a ${estado}. ` +
      `Permitidas desde ${existente.estado}: ` +
      `${(Soporte.TRANSICIONES[existente.estado] || []).join(", ") || "ninguna"}.`, 409);
  }

  try {
    await registrarEventoProceso({
      seudonimo_id: actualizado.seudonimo_id,
      correlacion_id: correlacionId,
      tipo: "SOLICITUD_ESTADO_ACTUALIZADO",
      detalle: { solicitud_id: id, nuevo_estado: estado, actor_id: actor?.sub || null },
    }, colEventos);
  } catch { /* trazabilidad degradada */ }

  return actualizado;
}

export async function listar({ estado, limite = 50, pagina = 1, colSoporte }) {
  if (estado && !Soporte.ESTADOS_SOLICITUD.includes(estado)) {
    throw new ErrorApi("PARAMETRO_INVALIDO",
      `Estado '${estado}' desconocido. Permitidos: ${Soporte.ESTADOS_SOLICITUD.join(", ")}.`, 400);
  }
  const lim = Math.min(Math.max(Number(limite) || 50, 1), 100);
  const pag = Math.max(Number(pagina) || 1, 1);

  const [elementos, total] = await Promise.all([
    Soporte.listarSolicitudes({ estado, limite: lim, pagina: pag }, colSoporte),
    Soporte.contarSolicitudes(estado ? { estado } : {}, colSoporte),
  ]);

  const totalPaginas = Math.max(1, Math.ceil(total / lim));
  return {
    solicitudes: elementos,
    paginacion: {
      pagina: pag, tamano: lim, total, total_paginas: totalPaginas,
      tiene_siguiente: pag < totalPaginas, tiene_anterior: pag > 1,
    },
  };
}
