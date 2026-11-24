import { Router } from "express";
import { autenticar } from "@bienestar/comun/autenticacion.js";
import { autorizar } from "@bienestar/comun/autorizacion.js";
import { PERMISOS } from "@bienestar/comun/catalogos-auditoria.js";
import { quiereXml } from "@bienestar/comun/errores.js";
import { aXml } from "@bienestar/comun/xmlizar.js";
import { contextoOperativo } from "@bienestar/comun/modelos/Usuario.js";

import * as servicio from "./servicio.js";

export const router = Router();

function responder(req, res, datos, { status = 200, rootTag = "cuestionario_respuesta" } = {}) {
  if (quiereXml(req)) {
    res.status(status).type("application/xml; charset=utf-8");
    return res.send(aXml(datos, rootTag));
  }
  return res.status(status).json(datos);
}

router.use(autenticar);

// Listar cuestionarios disponibles
router.get("/cuestionarios", autorizar(PERMISOS.AUTOREPORTE_RESPONDER, PERMISOS.INSTRUMENTO_ADMIN), async (req, res, next) => {
  try {
    const cuestionarios = await servicio.listarCuestionarios({ activo: req.query.activo });
    responder(req, res, { cuestionarios, total: cuestionarios.length }, { rootTag: "cuestionarios_respuesta" });
  } catch (err) {
    next(err);
  }
});

// Detalle de un cuestionario con preguntas y escalas
router.get("/cuestionarios/:id", autorizar(PERMISOS.AUTOREPORTE_RESPONDER, PERMISOS.INSTRUMENTO_ADMIN), async (req, res, next) => {
  try {
    const detalle = await servicio.obtenerCuestionario(req.params.id);
    responder(req, res, detalle, { rootTag: "cuestionario_detalle" });
  } catch (err) {
    next(err);
  }
});

// Recuperar borrador temporal de respuestas
router.get("/cuestionarios/:id/borrador", autorizar(PERMISOS.AUTOREPORTE_RESPONDER), async (req, res, next) => {
  try {
    const ctx = await contextoOperativo(req.actor?.sub || req.actor?.usuario_id);
    const borrador = await servicio.obtenerBorrador({
      cuestionario_id: req.params.id,
      seudonimo_id: ctx?.seudonimo_id,
    });
    responder(req, res, borrador, { rootTag: "borrador_encuesta" });
  } catch (err) {
    next(err);
  }
});

// Guardar o actualizar borrador temporal de respuestas
router.put("/cuestionarios/:id/borrador", autorizar(PERMISOS.AUTOREPORTE_RESPONDER), async (req, res, next) => {
  try {
    const ctx = await contextoOperativo(req.actor?.sub || req.actor?.usuario_id);
    const resultado = await servicio.guardarBorrador({
      cuestionario_id: req.params.id,
      seudonimo_id: ctx?.seudonimo_id,
      campania_id: req.body?.campania_id,
      respuestas: req.body?.respuestas,
    });
    responder(req, res, resultado, { rootTag: "borrador_guardado" });
  } catch (err) {
    next(err);
  }
});

// Captura definitiva de respuestas de encuesta
router.post("/cuestionarios/:id/respuestas", autorizar(PERMISOS.AUTOREPORTE_RESPONDER), async (req, res, next) => {
  try {
    const ctx = await contextoOperativo(req.actor?.sub || req.actor?.usuario_id);
    const resultado = await servicio.registrarRespuestas({
      cuestionario_id: req.params.id,
      campania_id: req.body?.campania_id,
      seudonimo_id: ctx?.seudonimo_id,
      respuestas: req.body?.respuestas,
      metadatos: req.body?.metadatos,
      comentario: req.body?.comentario,
      correlacionId: req.correlacionId,
      req,
    });
    responder(req, res, resultado, { status: 201, rootTag: "registro_respuesta" });
  } catch (err) {
    next(err);
  }
});
