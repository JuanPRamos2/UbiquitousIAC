import { Router } from "express";
import * as Portal from "../controladores/portal.controlador.js";
import { autenticar } from "../middlewares/autenticacion.js";
import { autorizar } from "../middlewares/autorizacion.js";
import { PERFILES } from "../utilidades/catalogos-auditoria.js";

export const portalRouter = Router();
portalRouter.use(autenticar);

portalRouter.get("/escritorio", Portal.escritorio);

portalRouter.get("/consentimiento", autorizar(PERFILES.COLABORADOR), Portal.miConsentimiento);
portalRouter.post("/consentimiento", autorizar(PERFILES.COLABORADOR), Portal.cambiarConsentimiento);

portalRouter.get("/mis-evaluaciones", autorizar(PERFILES.COLABORADOR), Portal.misEvaluaciones);

portalRouter.post("/soporte", autorizar(PERFILES.COLABORADOR), Portal.crearSoporte);
portalRouter.get(
  "/soporte",
  autorizar(PERFILES.AUDITOR, PERFILES.ADMINISTRADOR),
  Portal.listarSoporte
);

portalRouter.get("/cuentas", autorizar(PERFILES.ADMINISTRADOR), Portal.cuentas);

portalRouter.get(
  "/configuracion",
  autorizar(PERFILES.LIDER, PERFILES.ESPECIALISTA, PERFILES.AUDITOR, PERFILES.ADMINISTRADOR),
  Portal.configuracion
);
portalRouter.patch("/configuracion", autorizar(PERFILES.ADMINISTRADOR), Portal.guardarConfiguracion);
