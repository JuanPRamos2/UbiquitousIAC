import { Router } from "express";
import * as Auditoria from "../controladores/auditoria.controlador.js";
import { autenticar } from "../middlewares/autenticacion.js";
import { autorizar } from "../middlewares/autorizacion.js";
import { PERFILES } from "../utilidades/catalogos-auditoria.js";

export const auditoriaRouter = Router();
auditoriaRouter.get(
  "/consentimientos",
  autenticar,
  autorizar(PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Auditoria.listarEvidenciaConsentimiento
);
auditoriaRouter.get(
  "/consentimientos/:seudonimoId",
  autenticar,
  autorizar(PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Auditoria.historialConsentimiento
);
auditoriaRouter.get(
  "/soporte",
  autenticar,
  autorizar(PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Auditoria.listarSoporte
);
auditoriaRouter.get(
  "/",
  autenticar,
  autorizar(PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Auditoria.listar
);
