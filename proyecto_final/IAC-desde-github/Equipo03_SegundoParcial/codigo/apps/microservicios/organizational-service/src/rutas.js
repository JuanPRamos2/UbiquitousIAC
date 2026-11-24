import { Router } from "express";
import { autenticar } from "@bienestar/comun/autenticacion.js";
import { autorizar } from "@bienestar/comun/autorizacion.js";
import { PERMISOS } from "@bienestar/comun/catalogos-auditoria.js";
import { quiereXml } from "@bienestar/comun/errores.js";
import { aXml } from "@bienestar/comun/xmlizar.js";

import * as servicio from "./servicio.js";

export const router = Router();

function responder(req, res, datos, { status = 200, rootTag = "organizacion_respuesta" } = {}) {
  if (quiereXml(req)) {
    res.status(status).type("application/xml; charset=utf-8");
    return res.send(aXml(datos, rootTag));
  }
  return res.status(status).json(datos);
}

router.use(autenticar);

const PERMISOS_LECTURA = [
  PERMISOS.UNIDAD_ADMIN,
  PERMISOS.AGREGADO_UNIDAD,
  PERMISOS.AGREGADO_GLOBAL,
  PERMISOS.CAMPANIA_ADMIN,
];

// Listar unidades organizacionales
router.get("/organizacion/unidades", autorizar(...PERMISOS_LECTURA), async (req, res, next) => {
  try {
    const unidades = await servicio.listarUnidades({
      activa: req.query.activa,
      actor: req.actor,
    });
    responder(req, res, { unidades, total: unidades.length }, { rootTag: "unidades_respuesta" });
  } catch (err) {
    next(err);
  }
});

// Detalle de una unidad
router.get("/organizacion/unidades/:id", autorizar(...PERMISOS_LECTURA), async (req, res, next) => {
  try {
    const unidad = await servicio.obtenerUnidadPorId(req.params.id, { actor: req.actor });
    responder(req, res, { unidad }, { rootTag: "unidad_respuesta" });
  } catch (err) {
    next(err);
  }
});

// Arbol jerarquico completo (CTE recursivo)
router.get("/organizacion/unidades/:id/arbol", autorizar(...PERMISOS_LECTURA), async (req, res, next) => {
  try {
    const arbol = await servicio.obtenerArbolJerarquico(req.params.id, { actor: req.actor });
    responder(req, res, arbol, { rootTag: "arbol_organizacional_respuesta" });
  } catch (err) {
    next(err);
  }
});

// Alta de unidad organizacional (exige plantilla declarada >= 5)
router.post("/organizacion/unidades", autorizar(PERMISOS.UNIDAD_ADMIN), async (req, res, next) => {
  try {
    const creada = await servicio.crearUnidad({
      ...req.body,
      req,
    });
    responder(req, res, { unidad: creada }, { status: 201, rootTag: "unidad_respuesta" });
  } catch (err) {
    next(err);
  }
});

// Modificacion de unidad organizacional
router.put("/organizacion/unidades/:id", autorizar(PERMISOS.UNIDAD_ADMIN), async (req, res, next) => {
  try {
    const actualizada = await servicio.actualizarUnidad(req.params.id, req.body, { req });
    responder(req, res, { unidad: actualizada }, { rootTag: "unidad_respuesta" });
  } catch (err) {
    next(err);
  }
});

// Baja logica de unidad organizacional (valida dependencias)
router.delete("/organizacion/unidades/:id", autorizar(PERMISOS.UNIDAD_ADMIN), async (req, res, next) => {
  try {
    const eliminada = await servicio.eliminarUnidadLogica(req.params.id, { req });
    responder(req, res, { unidad: eliminada }, { rootTag: "unidad_respuesta" });
  } catch (err) {
    next(err);
  }
});
