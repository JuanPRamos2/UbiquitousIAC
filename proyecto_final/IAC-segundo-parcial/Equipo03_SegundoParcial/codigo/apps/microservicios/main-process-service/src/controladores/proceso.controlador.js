import { asinc } from "@bienestar/comun/servicio.js";
import { listarEventosProceso } from "@bienestar/comun/modelos/EventosProceso.js";

import * as ProcesoEncuesta from "../servicios/proceso-encuesta.servicio.js";
import * as SolicitudApoyo from "../servicios/solicitud-apoyo.servicio.js";
import { responderProceso } from "../utilidades/serializador.js";

export const registrarRespuesta = asinc(async (req, res) => {
  const resultado = await ProcesoEncuesta.registrarRespuesta({
    actor: req.actor, cuerpo: req.body, correlacionId: req.correlacionId,
  });
  responderProceso(req, res, resultado, { rootTag: "proceso_respuesta", status: 201 });
});

export const resumenAgregados = asinc(async (req, res) => {
  const resultado = await ProcesoEncuesta.resumenAgregados({ consulta: req.query });
  responderProceso(req, res, resultado, { rootTag: "agregados_resumen", status: 200 });
});

export const respuestasPropias = asinc(async (req, res) => {
  const resultado = await ProcesoEncuesta.respuestasPropias({ actor: req.actor });
  responderProceso(req, res, resultado, { rootTag: "participacion_propia", status: 200 });
});

export const crearSolicitud = asinc(async (req, res) => {
  const resultado = await SolicitudApoyo.crearSolicitud({
    actor: req.actor, mensaje: req.body?.mensaje, correlacionId: req.correlacionId,
  });
  responderProceso(req, res, resultado, { rootTag: "solicitud_apoyo", status: 201 });
});

export const actualizarEstadoSolicitud = asinc(async (req, res) => {
  const resultado = await SolicitudApoyo.actualizarEstado({
    id: req.params.id, estado: req.body?.estado, nota: req.body?.nota,
    actor: req.actor, correlacionId: req.correlacionId,
  });
  responderProceso(req, res, resultado, { rootTag: "solicitud_apoyo", status: 200 });
});

export const listarSolicitudes = asinc(async (req, res) => {
  const resultado = await SolicitudApoyo.listar({
    estado: req.query.estado,
    limite: req.query.tamano || req.query.limite,
    pagina: req.query.pagina,
  });
  responderProceso(req, res, resultado, { rootTag: "solicitudes_apoyo", status: 200 });
});

export const listarEventos = asinc(async (req, res) => {
  const eventos = await listarEventosProceso({
    seudonimo_id: req.query.seudonimo_id,
    correlacion_id: req.query.correlacion_id,
    tipo: req.query.tipo,
    limite: req.query.tamano || req.query.limite,
    pagina: req.query.pagina,
  });
  responderProceso(req, res, { total: eventos.length, eventos },
    { rootTag: "eventos_respuesta", status: 200 });
});
