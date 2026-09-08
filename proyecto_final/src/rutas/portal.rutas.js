import { Router } from "express";
import * as Portal from "../controladores/portal.controlador.js";
import { autenticar } from "../middlewares/autenticacion.js";
import { autorizar } from "../middlewares/autorizacion.js";
import { PERFILES } from "../utilidades/catalogos-auditoria.js";

export const portalRouter = Router();
portalRouter.use(autenticar);

portalRouter.get("/escritorio", Portal.escritorio);

portalRouter.get("/consentimiento", autorizar(PERFILES.COLAB), Portal.miConsentimiento);
portalRouter.post("/consentimiento", autorizar(PERFILES.COLAB), Portal.cambiarConsentimiento);

portalRouter.get("/mis-evaluaciones", autorizar(PERFILES.COLAB), Portal.misEvaluaciones);

portalRouter.post("/soporte", autorizar(PERFILES.COLAB), Portal.crearSoporte);
portalRouter.get(
  "/soporte",
  autorizar(PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Portal.listarSoporte
);

portalRouter.get("/cuentas", autorizar(PERFILES.ADMIN_SISTEMA), Portal.cuentas);

portalRouter.get(
  "/configuracion",
  autorizar(PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Portal.configuracion
);
portalRouter.patch("/configuracion", autorizar(PERFILES.ADMIN_SISTEMA), Portal.guardarConfiguracion);
