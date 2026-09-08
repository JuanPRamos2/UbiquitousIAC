import { Router } from "express";
import * as Catalogo from "../controladores/catalogo.controlador.js";
import { autenticar } from "../middlewares/autenticacion.js";
import { autorizar } from "../middlewares/autorizacion.js";
import { PERFILES } from "../utilidades/catalogos-auditoria.js";

export const catalogoRouter = Router();
catalogoRouter.use(autenticar);

catalogoRouter.get(
  "/unidades",
  autorizar(PERFILES.COLAB, PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Catalogo.unidades
);
catalogoRouter.get(
  "/campanias",
  autorizar(PERFILES.COLAB, PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Catalogo.campanias
);
catalogoRouter.get(
  "/instrumentos",
  autorizar(PERFILES.COLAB, PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Catalogo.instrumentos
);
catalogoRouter.get(
  "/instrumentos/:instrumento_id/versiones/:version/reactivos",
  autorizar(PERFILES.COLAB, PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Catalogo.reactivos
);
catalogoRouter.get(
  "/versiones-consentimiento",
  autorizar(PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Catalogo.versionesConsentimiento
);
catalogoRouter.get("/cuentas", autorizar(PERFILES.ADMIN_SISTEMA), Catalogo.cuentas);
