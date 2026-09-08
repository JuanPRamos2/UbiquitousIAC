import { Router } from "express";
import * as Agregado from "../controladores/agregado.controlador.js";
import { autenticar } from "../middlewares/autenticacion.js";
import { autorizar } from "../middlewares/autorizacion.js";
import { PERFILES } from "../utilidades/catalogos-auditoria.js";

export const agregadoRouter = Router();
agregadoRouter.get(
  "/parametros/k",
  autenticar,
  autorizar(PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Agregado.leerK
);
agregadoRouter.patch(
  "/parametros/k",
  autenticar,
  autorizar(PERFILES.ADMIN_SISTEMA),
  Agregado.cambiarK
);
agregadoRouter.get(
  "/parametros",
  autenticar,
  autorizar(PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Agregado.leerParametros
);
agregadoRouter.patch(
  "/parametros",
  autenticar,
  autorizar(PERFILES.ADMIN_SISTEMA),
  Agregado.guardarParametros
);
agregadoRouter.get(
  "/:unidadId/:campaniaId",
  autenticar,
  autorizar(PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Agregado.consultar
);
