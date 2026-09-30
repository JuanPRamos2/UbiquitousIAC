import { Router } from "express";
import * as Encuesta from "../controladores/encuesta.controlador.js";
import { autenticar } from "../middlewares/autenticacion.js";
import { autorizar } from "../middlewares/autorizacion.js";
import { PERFILES } from "../utilidades/catalogos-auditoria.js";

export const encuestaRouter = Router();
encuestaRouter.get(
  "/estado",
  autenticar,
  autorizar(PERFILES.COLABORADOR),
  Encuesta.estado
);
encuestaRouter.get(
  "/consentimiento",
  autenticar,
  autorizar(PERFILES.COLABORADOR),
  Encuesta.miConsentimiento
);
encuestaRouter.post(
  "/consentimiento",
  autenticar,
  autorizar(PERFILES.COLABORADOR),
  Encuesta.cambiarConsentimiento
);
encuestaRouter.get("/mias", autenticar, autorizar(PERFILES.COLABORADOR), Encuesta.mias);
encuestaRouter.get("/mis-accesos", autenticar, autorizar(PERFILES.COLABORADOR), Encuesta.misAccesos);
encuestaRouter.post(
  "/soporte",
  autenticar,
  autorizar(PERFILES.COLABORADOR),
  Encuesta.crearSoporte
);
encuestaRouter.post(
  "/respuestas",
  autenticar,
  autorizar(PERFILES.COLABORADOR),
  Encuesta.crear
);
