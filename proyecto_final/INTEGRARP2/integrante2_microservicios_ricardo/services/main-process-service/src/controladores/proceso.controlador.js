import * as ProcesoEncuesta from "../servicios/proceso-encuesta.servicio.js";
import * as SolicitudApoyo from "../servicios/solicitud-apoyo.servicio.js";
import { listarEventosProceso } from "../../../../src/modelos/EventosProceso.js";
import { responderProceso } from "../utilidades/serializador.js";

export async function registrarRespuesta(req, res, next) {
  try {
    const resultado = await ProcesoEncuesta.registrarRespuesta({
      actor: req.actor,
      body: req.body,
      correlacionId: req.correlacionId,
    });
    return responderProceso(req, res, resultado, { rootTag: "proceso_respuesta", status: 201 });
  } catch (err) {
    next(err);
  }
}

export async function resumenAgregados(req, res, next) {
  try {
    const resultado = await ProcesoEncuesta.resumenAgregados(req.query);
    return responderProceso(req, res, resultado, { rootTag: "agregados_resumen", status: 200 });
  } catch (err) {
    next(err);
  }
}

export async function crearSolicitud(req, res, next) {
  try {
    const resultado = await SolicitudApoyo.crearSolicitud({
      actor: req.actor,
      mensaje: req.body?.mensaje,
      correlacionId: req.correlacionId,
    });
    return responderProceso(req, res, resultado, { rootTag: "solicitud_apoyo", status: 201 });
  } catch (err) {
    next(err);
  }
}

export async function actualizarEstadoSolicitud(req, res, next) {
  try {
    const resultado = await SolicitudApoyo.actualizarEstado({
      id: req.params.id,
      estado: req.body?.estado,
      nota: req.body?.nota,
      actor: req.actor,
      correlacionId: req.correlacionId,
    });
    return responderProceso(req, res, resultado, { rootTag: "solicitud_apoyo", status: 200 });
  } catch (err) {
    next(err);
  }
}

export async function listarSolicitudes(req, res, next) {
  try {
    const resultado = await SolicitudApoyo.listar(req.query);
    return responderProceso(req, res, resultado, { rootTag: "solicitudes_apoyo", status: 200 });
  } catch (err) {
    next(err);
  }
}

export async function listarEventos(req, res, next) {
  try {
    const eventos = await listarEventosProceso(req.query);
    return responderProceso(req, res, { data: eventos }, { rootTag: "eventos_proceso", status: 200 });
  } catch (err) {
    next(err);
  }
}
