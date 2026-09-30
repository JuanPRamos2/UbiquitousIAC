import { Router } from "express";
import * as Agregado from "../controladores/agregado.controlador.js";
import { autenticar } from "../middlewares/autenticacion.js";
import { autorizar } from "../middlewares/autorizacion.js";
import { PERFILES } from "../utilidades/catalogos-auditoria.js";

export const agregadoRouter = Router();
agregadoRouter.get(
  "/parametros/k",
  autenticar,
  autorizar(PERFILES.LIDER, PERFILES.ESPECIALISTA, PERFILES.AUDITOR, PERFILES.ADMINISTRADOR),
  Agregado.leerK
);
agregadoRouter.patch(
  "/parametros/k",
  autenticar,
  autorizar(PERFILES.ADMINISTRADOR),
  Agregado.cambiarK
);
agregadoRouter.get(
  "/parametros",
  autenticar,
  autorizar(PERFILES.LIDER, PERFILES.ESPECIALISTA, PERFILES.AUDITOR, PERFILES.ADMINISTRADOR),
  Agregado.leerParametros
);
agregadoRouter.patch(
  "/parametros",
  autenticar,
  autorizar(PERFILES.ADMINISTRADOR),
  Agregado.guardarParametros
);
agregadoRouter.get(
  "/:unidadId/:campaniaId",
  autenticar,
  autorizar(PERFILES.LIDER, PERFILES.ESPECIALISTA, PERFILES.AUDITOR, PERFILES.ADMINISTRADOR),
  Agregado.consultar
);
