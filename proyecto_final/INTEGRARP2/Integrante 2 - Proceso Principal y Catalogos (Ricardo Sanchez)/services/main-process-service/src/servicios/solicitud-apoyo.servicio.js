import * as Soporte from "../../../../src/modelos/Soporte.js";
import * as Usuario from "../../../../src/modelos/Usuario.js";
import { registrarEventoProceso } from "../../../../src/modelos/EventosProceso.js";
import { HttpError } from "../../../../src/utilidades/errores.js";

/**
 * Servicio para gestión operativa de solicitudes de apoyo (Integrante 2).
 * Gestiona ciclo de vida (ABIERTA -> EN_PROCESO -> CERRADA), historial append,
 * y emisión de eventos sin comprometer la identidad (D-01).
 */

export async function crearSolicitud({ actor, mensaje, correlacionId, colSoporte, colEventos, ctxUsuario }) {
  const texto = String(mensaje || "").trim();
  if (texto.length < 8) {
    throw new HttpError(400, "PAYLOAD_INVALIDO", "Escriba una solicitud con más detalle (mínimo 8 caracteres)");
  }

  const ctx = ctxUsuario || (await Usuario.contextoOperativo(actor.usuario_id));
  if (!ctx?.seudonimo_id) {
    throw new HttpError(403, "SIN_SEUDONIMO", "Su cuenta no tiene participación operativa");
  }

  const doc = await Soporte.crearSolicitud(
    {
      seudonimo_id: ctx.seudonimo_id,
      mensaje: texto.slice(0, 1000),
    },
    colSoporte
  );

  const evento = await registrarEventoProceso(
    {
      seudonimo_id: ctx.seudonimo_id,
      correlacion_id: correlacionId,
      tipo: "SOLICITUD_CREADA",
      detalle: {
        solicitud_id: doc.id,
      },
    },
    colEventos
  );

  return {
    id: doc.id,
    fecha: doc.fecha,
    estado: doc.estado || "ABIERTA",
    historial: doc.historial || [],
    evento_id: String(evento._id || evento.id || ""),
  };
}

export async function actualizarEstado({ id, estado, nota, actor, correlacionId, colSoporte, colEventos }) {
  if (!id) {
    throw new HttpError(400, "PAYLOAD_INVALIDO", "El identificador de la solicitud es obligatorio");
  }

  if (!Soporte.ESTADOS_SOLICITUD.includes(estado)) {
    throw new HttpError(
      400,
      "ESTADO_INVALIDO",
      `Estado inválido: ${estado}. Valores permitidos: ${Soporte.ESTADOS_SOLICITUD.join(", ")}`
    );
  }

  const actualizado = await Soporte.actualizarEstadoSolicitud(
    {
      id,
      estado,
      actor_id: actor.usuario_id,
      nota: nota ? String(nota).trim() : undefined,
    },
    colSoporte
  );

  if (!actualizado) {
    throw new HttpError(404, "SOLICITUD_NO_ENCONTRADA", "No se encontró la solicitud de apoyo solicitada");
  }

  await registrarEventoProceso(
    {
      correlacion_id: correlacionId,
      tipo: "SOLICITUD_ESTADO_ACTUALIZADO",
      detalle: {
        solicitud_id: id,
        nuevo_estado: estado,
        actor_id: actor.usuario_id,
      },
    },
    colEventos
  ).catch((err) => console.error("Error registrando evento:", err.message));

  return actualizado;
}

export async function listar({ estado, limite = 50, pagina = 1, colSoporte }) {
  const limiteNum = Math.min(Math.max(Number(limite) || 50, 1), 200);
  const paginaNum = Math.max(Number(pagina) || 1, 1);

  if (estado && !Soporte.ESTADOS_SOLICITUD.includes(estado)) {
    throw new HttpError(
      400,
      "FILTRO_INVALIDO",
      `Estado desconocido: ${estado}. Valores permitidos: ${Soporte.ESTADOS_SOLICITUD.join(", ")}`
    );
  }

  const items = await Soporte.listarSolicitudes(
    {
      estado,
      limite: limiteNum,
      pagina: paginaNum,
    },
    colSoporte
  );

  return {
    pagina: paginaNum,
    limite: limiteNum,
    total: items.length,
    data: items,
  };
}
