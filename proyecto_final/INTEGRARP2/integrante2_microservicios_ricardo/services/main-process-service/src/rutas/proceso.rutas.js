import { Router } from "express";
import * as Proceso from "../controladores/proceso.controlador.js";
import { autenticar } from "../../../../src/middlewares/autenticacion.js";
import { autorizar } from "../../../../src/middlewares/autorizacion.js";
import { PERFILES } from "../../../../src/utilidades/catalogos-auditoria.js";

export const procesoV1Router = Router();

procesoV1Router.use(autenticar);

// ==========================================
// PROCESO DE EVALUACIÓN Y RESPUESTAS (D-01)
// ==========================================
procesoV1Router.post(
  "/encuestas/respuestas",
  autorizar(PERFILES.COLAB),
  Proceso.registrarRespuesta
);

procesoV1Router.get(
  "/encuestas/agregados/resumen",
  autorizar(PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Proceso.resumenAgregados
);

// ==========================================
// SOLICITUDES DE APOYO (CICLO DE VIDA)
// ==========================================
procesoV1Router.post(
  "/solicitudes-apoyo",
  autorizar(PERFILES.COLAB),
  Proceso.crearSolicitud
);

procesoV1Router.patch(
  "/solicitudes-apoyo/:id/estado",
  autorizar(PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Proceso.actualizarEstadoSolicitud
);

procesoV1Router.get(
  "/solicitudes-apoyo",
  autorizar(PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Proceso.listarSolicitudes
);

// ==========================================
// TRAZABILIDAD DE EVENTOS DE PROCESO
// ==========================================
procesoV1Router.get(
  "/eventos-proceso",
  autorizar(PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Proceso.listarEventos
);
