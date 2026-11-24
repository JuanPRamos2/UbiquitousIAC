import { Router } from "express";
import { autenticar } from "@bienestar/comun/autenticacion.js";
import { autorizar } from "@bienestar/comun/autorizacion.js";
import { PERMISOS } from "@bienestar/comun/catalogos-auditoria.js";
import { quiereXml } from "@bienestar/comun/errores.js";
import { aXml } from "@bienestar/comun/xmlizar.js";

import * as servicio from "./servicio.js";

export const router = Router();

function responder(req, res, datos, { status = 200, rootTag = "apoyo_respuesta" } = {}) {
  if (quiereXml(req)) {
    res.status(status).type("application/xml; charset=utf-8");
    return res.send(aXml(datos, rootTag));
  }
  return res.status(status).json(datos);
}

router.use(autenticar);

// Alta voluntaria de solicitud de apoyo emocional
router.post("/apoyo/solicitudes", autorizar(PERMISOS.APOYO_SOLICITAR, PERMISOS.AUTOREPORTE_RESPONDER), async (req, res, next) => {
  try {
    const doc = await servicio.crearSolicitud({
      actor: req.actor,
      mensaje: req.body?.mensaje,
      correlacionId: req.correlacionId,
      req,
    });
    responder(req, res, doc, { status: 201, rootTag: "solicitud_apoyo" });
  } catch (err) {
    next(err);
  }
});

// Listado de solicitudes reservado a especialistas autorizados
router.get("/apoyo/solicitudes", autorizar(PERMISOS.APOYO_ATENDER), async (req, res, next) => {
  try {
    const resultado = await servicio.listarSolicitudes({
      estado: req.query.estado,
      pagina: req.query.pagina,
      tamano: req.query.tamano,
    });
    responder(req, res, resultado, { rootTag: "solicitudes_apoyo" });
  } catch (err) {
    next(err);
  }
});

// Detalle de solicitud
router.get("/apoyo/solicitudes/:id", autorizar(PERMISOS.APOYO_ATENDER, PERMISOS.APOYO_SOLICITAR), async (req, res, next) => {
  try {
    const doc = await servicio.obtenerSolicitudPorId({
      id: req.params.id,
      actor: req.actor,
    });
    responder(req, res, doc, { rootTag: "solicitud_apoyo" });
  } catch (err) {
    next(err);
  }
});

// Actualizacion de estado de atencion
router.put("/apoyo/solicitudes/:id/estado", autorizar(PERMISOS.APOYO_ATENDER), async (req, res, next) => {
  try {
    const doc = await servicio.actualizarEstadoSolicitud({
      id: req.params.id,
      estado: req.body?.estado,
      nota: req.body?.nota,
      actor: req.actor,
      req,
    });
    responder(req, res, doc, { rootTag: "solicitud_apoyo" });
  } catch (err) {
    next(err);
  }
});

// Mensaje de seguimiento o conversacion protegida
router.post("/apoyo/solicitudes/:id/mensajes", autorizar(PERMISOS.APOYO_ATENDER, PERMISOS.APOYO_SOLICITAR), async (req, res, next) => {
  try {
    const doc = await servicio.agregarMensajeSeguimiento({
      id: req.params.id,
      mensaje: req.body?.mensaje,
      actor: req.actor,
    });
    responder(req, res, doc, { status: 201, rootTag: "mensaje_apoyo_respuesta" });
  } catch (err) {
    next(err);
  }
});
