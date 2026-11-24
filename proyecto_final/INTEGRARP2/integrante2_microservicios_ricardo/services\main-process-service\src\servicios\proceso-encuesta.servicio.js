import * as EncuestaServicio from "../../../../src/servicios/encuesta.servicio.js";
import * as EncuestaModelo from "../../../../src/modelos/Encuesta.js";
import { registrarEventoProceso } from "../../../../src/modelos/EventosProceso.js";
import { HttpError } from "../../../../src/utilidades/errores.js";

/**
 * Servicio de proceso principal de encuestas (Integrante 2).
 * Reutiliza las validaciones de PostgreSQL y el modelo MongoDB existente,
 * asegurando la emisión de eventos de proceso y la regla D-01 (sin empleado_id).
 */

export async function registrarRespuesta({ actor, body, correlacionId, colEventos, colRespuestas }) {
  if (!body) {
    throw new HttpError(400, "PAYLOAD_INVALIDO", "El cuerpo de la solicitud es obligatorio");
  }

  // Regla D-01: Prohibido estrictamente aceptar o persistir empleado_id en la carga de respuestas
  if ("empleado_id" in body) {
    throw new HttpError(400, "PRIVACIDAD_D01", "Violación de regla D-01: No se permite empleado_id en este microservicio");
  }

  // Delegar en el servicio de negocio existente (validación Postgres + guardado Mongo + bitácora Postgres)
  const resultado = await EncuestaServicio.guardarAutoreporte({
    actor,
    body,
    correlacionId,
  });

  // Emisión obligatoria del evento de proceso correlacionado
  const evento = await registrarEventoProceso(
    {
      seudonimo_id: body.seudonimo_id,
      correlacion_id: correlacionId,
      tipo: "RESPUESTA_REGISTRADA",
      detalle: {
        respuesta_id: resultado.id,
        campania_id: resultado.campania_id,
        instrumento_id: resultado.instrumento_id,
        version_instrumento: resultado.version_instrumento,
      },
    },
    colEventos
  );

  return {
    ...resultado,
    evento_id: String(evento._id || evento.id || ""),
  };
}

export async function resumenAgregados({ campaniaId, desde, hasta, col }) {
  const filtros = {};
  if (campaniaId !== undefined && campaniaId !== null && !isNaN(Number(campaniaId))) {
    filtros.campaniaId = Number(campaniaId);
  }
  if (desde) filtros.desde = desde;
  if (hasta) filtros.hasta = hasta;

  const grupos = await EncuestaModelo.agregarRespuestasPorUnidadCampania(filtros, col);
  return {
    total_grupos: grupos.length,
    campania_id: filtros.campaniaId || null,
    resumen: grupos,
  };
}
