import { Router } from "express";
import * as Catalogo from "../controladores/catalogo.controlador.js";
import { autenticar } from "../middlewares/autenticacion.js";
import { autorizar } from "../middlewares/autorizacion.js";
import { PERFILES } from "../utilidades/catalogos-auditoria.js";

export const catalogoRouter = Router();
catalogoRouter.use(autenticar);

catalogoRouter.get(
  "/unidades",
  autorizar(PERFILES.COLABORADOR, PERFILES.LIDER, PERFILES.ESPECIALISTA, PERFILES.AUDITOR, PERFILES.ADMINISTRADOR),
  Catalogo.unidades
);
catalogoRouter.get(
  "/campanias",
  autorizar(PERFILES.COLABORADOR, PERFILES.LIDER, PERFILES.ESPECIALISTA, PERFILES.AUDITOR, PERFILES.ADMINISTRADOR),
  Catalogo.campanias
);
catalogoRouter.get(
  "/instrumentos",
  autorizar(PERFILES.COLABORADOR, PERFILES.LIDER, PERFILES.ESPECIALISTA, PERFILES.AUDITOR, PERFILES.ADMINISTRADOR),
  Catalogo.instrumentos
);
catalogoRouter.get(
  "/instrumentos/:instrumento_id/versiones/:version/reactivos",
  autorizar(PERFILES.COLABORADOR, PERFILES.LIDER, PERFILES.ESPECIALISTA, PERFILES.AUDITOR, PERFILES.ADMINISTRADOR),
  Catalogo.reactivos
);
catalogoRouter.get(
  "/versiones-consentimiento",
  autorizar(PERFILES.AUDITOR, PERFILES.ADMINISTRADOR),
  Catalogo.versionesConsentimiento
);
catalogoRouter.get("/cuentas", autorizar(PERFILES.ADMINISTRADOR), Catalogo.cuentas);
