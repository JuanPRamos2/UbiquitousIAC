import { Router } from "express";
import * as Encuesta from "../controladores/encuesta.controlador.js";
import { autenticar } from "../middlewares/autenticacion.js";
import { autorizar } from "../middlewares/autorizacion.js";
import { PERFILES } from "../utilidades/catalogos-auditoria.js";

export const encuestaRouter = Router();
encuestaRouter.get(
  "/estado",
  autenticar,
  autorizar(PERFILES.COLAB),
  Encuesta.estado
);
encuestaRouter.get(
  "/consentimiento",
  autenticar,
  autorizar(PERFILES.COLAB),
  Encuesta.miConsentimiento
);
encuestaRouter.post(
  "/consentimiento",
  autenticar,
  autorizar(PERFILES.COLAB),
  Encuesta.cambiarConsentimiento
);
encuestaRouter.get("/mias", autenticar, autorizar(PERFILES.COLAB), Encuesta.mias);
encuestaRouter.get("/mis-accesos", autenticar, autorizar(PERFILES.COLAB), Encuesta.misAccesos);
encuestaRouter.post(
  "/soporte",
  autenticar,
  autorizar(PERFILES.COLAB),
  Encuesta.crearSoporte
);
encuestaRouter.post(
  "/respuestas",
  autenticar,
  autorizar(PERFILES.COLAB),
  Encuesta.crear
);
