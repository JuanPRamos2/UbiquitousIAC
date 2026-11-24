/**
 * Rutas versionadas de main-process-service: /api/v1/...
 *
 * Es el proceso principal del negocio: responder una campania y pedir
 * apoyo. La autorizacion se expresa con permisos de usuarios.permiso.
 *
 * APOYO_SOLICITAR y APOYO_ATENDER son permisos distintos a proposito:
 * quien puede pedir apoyo no debe poder leer las solicitudes de los
 * demas, y quien las atiende no necesita poder crearlas en nombre de
 * nadie.
 */
import { Router } from "express";

import { autenticar } from "@bienestar/comun/autenticacion.js";
import { autorizar } from "@bienestar/comun/autorizacion.js";
import { PERMISOS } from "@bienestar/comun/catalogos-auditoria.js";
import { limiteConsumo } from "@bienestar/comun/servicio.js";

import * as Proceso from "../controladores/proceso.controlador.js";

export const procesoV1Router = Router();

procesoV1Router.use(autenticar);
// El limite es mas estrecho que en catalogos: aqui cada peticion escribe.
procesoV1Router.use(limiteConsumo(60, 60));

// ------------------------------------- proceso de evaluacion (RN-01, RN-02)
procesoV1Router.post("/encuestas/respuestas",
  autorizar(PERMISOS.AUTOREPORTE_RESPONDER), Proceso.registrarRespuesta);

procesoV1Router.get("/encuestas/agregados/resumen",
  autorizar(PERMISOS.AGREGADO_UNIDAD, PERMISOS.AGREGADO_GLOBAL),
  Proceso.resumenAgregados);

procesoV1Router.get("/encuestas/respuestas/propias",
  autorizar(PERMISOS.PARTICIPACION_PROPIA), Proceso.respuestasPropias);

// --------------------------------------- solicitudes de apoyo (ciclo de vida)
procesoV1Router.post("/solicitudes-apoyo",
  autorizar(PERMISOS.APOYO_SOLICITAR), Proceso.crearSolicitud);

procesoV1Router.get("/solicitudes-apoyo",
  autorizar(PERMISOS.APOYO_ATENDER), Proceso.listarSolicitudes);

procesoV1Router.patch("/solicitudes-apoyo/:id/estado",
  autorizar(PERMISOS.APOYO_ATENDER), Proceso.actualizarEstadoSolicitud);

// ------------------------------------------- trazabilidad de los eventos
procesoV1Router.get("/eventos-proceso",
  autorizar(PERMISOS.BITACORA_CONSULTAR), Proceso.listarEventos);
