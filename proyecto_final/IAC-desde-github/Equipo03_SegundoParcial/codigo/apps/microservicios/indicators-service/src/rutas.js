import { Router } from "express";
import { autenticar } from "@bienestar/comun/autenticacion.js";
import { autorizar } from "@bienestar/comun/autorizacion.js";
import { PERMISOS } from "@bienestar/comun/catalogos-auditoria.js";
import { quiereXml } from "@bienestar/comun/errores.js";
import { aXml } from "@bienestar/comun/xmlizar.js";

import * as servicio from "./servicio.js";

export const router = Router();

function responder(req, res, datos, { status = 200, rootTag = "indicadores_respuesta" } = {}) {
  if (quiereXml(req)) {
    res.status(status).type("application/xml; charset=utf-8");
    return res.send(aXml(datos, rootTag));
  }
  return res.status(status).json(datos);
}

router.use(autenticar);

// Catalogo de indicadores autorizados
router.get("/indicadores", autorizar(PERMISOS.AGREGADO_UNIDAD, PERMISOS.AGREGADO_GLOBAL, PERMISOS.AUTOREPORTE_RESPONDER), async (req, res, next) => {
  try {
    const indicadores = await servicio.listarCatalogoIndicadores();
    responder(req, res, { indicadores, total: indicadores.length }, { rootTag: "indicadores_catalogo" });
  } catch (err) {
    next(err);
  }
});

// Consulta de indicadores agregados protegidos (umbral k >= 5)
router.get("/indicadores/agregados", autorizar(PERMISOS.AGREGADO_UNIDAD, PERMISOS.AGREGADO_GLOBAL), async (req, res, next) => {
  try {
    const resultado = await servicio.consultarAgregados({
      campania_id: req.query.campania_id,
      unidad_id: req.query.unidad_id,
      actor: req.actor,
      req,
    });
    responder(req, res, resultado, { rootTag: "agregados_respuesta" });
  } catch (err) {
    next(err);
  }
});

// Serie historica de evolucion temporal
router.get("/indicadores/historico", autorizar(PERMISOS.TENDENCIA_CONSULTAR, PERMISOS.AGREGADO_UNIDAD, PERMISOS.AGREGADO_GLOBAL), async (req, res, next) => {
  try {
    const resultado = await servicio.consultarHistorico({
      unidad_id: req.query.unidad_id,
      dimension_id: req.query.dimension_id,
      actor: req.actor,
    });
    responder(req, res, resultado, { rootTag: "historico_respuesta" });
  } catch (err) {
    next(err);
  }
});

// Recalculo o consolidacion de indicadores
router.post("/indicadores/calcular", autorizar(PERMISOS.CAMPANIA_ADMIN, PERMISOS.PARAMETRO_ADMIN), async (req, res, next) => {
  try {
    const resultado = await servicio.calcularIndicadoresCampania({
      campania_id: req.body?.campania_id,
      actor: req.actor,
      req,
    });
    responder(req, res, resultado, { rootTag: "calculo_respuesta" });
  } catch (err) {
    next(err);
  }
});
