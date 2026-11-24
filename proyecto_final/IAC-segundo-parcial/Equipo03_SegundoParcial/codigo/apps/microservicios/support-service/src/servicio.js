/**
 * Logica de dominio para support-service (Puerto 8116).
 *
 * Administra el ciclo de vida confidencial de solicitudes de apoyo emocional.
 * Restringe la atencion exclusivamente a especialistas y aisla la identidad
 * mediante seudonimos conforme a la regla D-01.
 */
import { ErrorApi } from "@bienestar/comun/errores.js";
import { base, verificarSinIdentidad } from "@bienestar/comun/mongo.js";
import { contextoOperativo } from "@bienestar/comun/modelos/Usuario.js";
import * as Soporte from "@bienestar/comun/modelos/Soporte.js";
import { texto } from "@bienestar/comun/validacion.js";
import { registrarBitacora } from "@bienestar/comun/auditoria.js";

const MIN_MENSAJE = 8;
const MAX_MENSAJE = 1000;

export async function crearSolicitud({ actor, mensaje, correlacionId, req = null, colSoporte = null }) {
  const txt = texto(mensaje, "mensaje", { minLong: MIN_MENSAJE, maxLong: MAX_MENSAJE });

  // Resolver el seudonimo operativo del colaborador
  const ctx = await contextoOperativo(actor?.sub || actor?.usuario_id);
  if (!ctx?.seudonimo_id) {
    throw new ErrorApi("SIN_SEUDONIMO", "La cuenta no tiene asignado un seudonimo operativo para solicitar apoyo.", 403);
  }

  const doc = await Soporte.crearSolicitud(
    {
      seudonimo_id: ctx.seudonimo_id,
      mensaje: txt,
      correlacion_id: correlacionId || "",
    },
    colSoporte
  );

  if (req) {
    await registrarBitacora(req, "CATALOGO_MODIFICADO", "EXITO", {
      tipo_recurso: "solicitud_apoyo",
      recurso_id: doc.id,
    });
  }

  return doc;
}

export async function listarSolicitudes({ estado = null, pagina = 1, tamano = 50, colSoporte = null }) {
  if (estado && !Soporte.ESTADOS_SOLICITUD.includes(estado)) {
    throw new ErrorApi("ESTADO_INVALIDO", `Estado '${estado}' no valido. Permitidos: ${Soporte.ESTADOS_SOLICITUD.join(", ")}.`, 400);
  }

  const lim = Math.min(Math.max(Number(tamano) || 50, 1), 100);
  const pag = Math.max(Number(pagina) || 1, 1);

  const [solicitudes, total] = await Promise.all([
    Soporte.listarSolicitudes({ estado, limite: lim, pagina: pag }, colSoporte),
    Soporte.contarSolicitudes(estado ? { estado } : {}, colSoporte),
  ]);

  const totalPaginas = Math.max(1, Math.ceil(total / lim));
  return {
    solicitudes,
    total,
    paginacion: {
      pagina: pag,
      tamano: lim,
      total,
      total_paginas: totalPaginas,
    },
  };
}

export async function obtenerSolicitudPorId({ id, actor, colSoporte = null }) {
  const solId = texto(id, "id");
  const doc = await Soporte.obtenerSolicitud(solId, colSoporte);
  if (!doc) {
    throw new ErrorApi("SOLICITUD_NO_ENCONTRADA", `No existe la solicitud '${solId}'.`, 404);
  }

  // Si el actor es COLABORADOR, solo puede ver su propia solicitud
  const perfil = String(actor?.perfil || "").toLowerCase();
  if (!perfil.includes("especialista")) {
    const ctx = await contextoOperativo(actor?.sub || actor?.usuario_id);
    if (doc.seudonimo_id !== ctx?.seudonimo_id) {
      throw new ErrorApi("SIN_PERMISO", "No tiene autorizacion para consultar una solicitud ajena.", 403);
    }
  }

  return doc;
}

export async function actualizarEstadoSolicitud({ id, estado, nota, actor, req = null, colSoporte = null }) {
  const solId = texto(id, "id");
  const nuevoEstado = texto(estado, "estado");

  if (!Soporte.ESTADOS_SOLICITUD.includes(nuevoEstado)) {
    throw new ErrorApi("ESTADO_INVALIDO", `Estado '${nuevoEstado}' no valido. Permitidos: ${Soporte.ESTADOS_SOLICITUD.join(", ")}.`, 400);
  }

  const actualizado = await Soporte.actualizarEstadoSolicitud(
    {
      id: solId,
      estado: nuevoEstado,
      actor_id: actor?.sub || actor?.usuario_id || "ESPECIALISTA",
      nota: nota ? String(nota).trim() : undefined,
    },
    colSoporte
  );

  if (!actualizado) {
    const existente = await Soporte.obtenerSolicitud(solId, colSoporte);
    if (!existente) {
      throw new ErrorApi("SOLICITUD_NO_ENCONTRADA", `No existe la solicitud '${solId}'.`, 404);
    }
    throw new ErrorApi(
      "TRANSICION_NO_PERMITIDA",
      `Una solicitud en estado '${existente.estado}' no puede transicionar a '${nuevoEstado}'.`,
      409
    );
  }

  if (req) {
    await registrarBitacora(req, "CATALOGO_MODIFICADO", "EXITO", {
      tipo_recurso: "solicitud_apoyo",
      recurso_id: solId,
    });
  }

  return actualizado;
}

export async function agregarMensajeSeguimiento({ id, mensaje, actor, dbMongo = null }) {
  const solId = texto(id, "id");
  const txt = texto(mensaje, "mensaje", { minLong: 3, maxLong: 1000 });

  const mdb = dbMongo || base();
  const col = mdb.collection("comunicaciones_apoyo");

  const doc = {
    solicitud_id: solId,
    emisor_rol: actor?.perfil || "COLABORADOR",
    emisor_id: actor?.sub || actor?.usuario_id || "ANONIMO",
    mensaje: txt,
    fecha: new Date(),
  };

  verificarSinIdentidad(doc);
  await col.insertOne(doc);

  return {
    resultado: "ENVIADO",
    solicitud_id: solId,
    mensaje: "Mensaje agregado al expediente confidencial de apoyo.",
    fecha: doc.fecha,
  };
}
