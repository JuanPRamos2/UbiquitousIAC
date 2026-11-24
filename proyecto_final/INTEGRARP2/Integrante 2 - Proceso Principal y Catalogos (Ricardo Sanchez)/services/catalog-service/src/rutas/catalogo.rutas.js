import { Router } from "express";
import * as Unidad from "../controladores/unidad.controlador.js";
import * as Instrumento from "../controladores/instrumento.controlador.js";
import * as Reactivo from "../controladores/reactivo.controlador.js";
import * as Campania from "../controladores/campania.controlador.js";
import { autenticar } from "../../../../src/middlewares/autenticacion.js";
import { autorizar } from "../../../../src/middlewares/autorizacion.js";
import { PERFILES } from "../../../../src/utilidades/catalogos-auditoria.js";

export const catalogoV1Router = Router();

// Middleware de autenticación para todas las operaciones de catálogos
catalogoV1Router.use(autenticar);

// ==========================================
// UNIDADES ORGANIZACIONALES
// ==========================================
catalogoV1Router.get(
  "/unidades",
  autorizar(PERFILES.COLAB, PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Unidad.listar
);
catalogoV1Router.get(
  "/unidades/:id",
  autorizar(PERFILES.COLAB, PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Unidad.obtenerPorId
);
catalogoV1Router.post(
  "/unidades",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Unidad.crear
);
catalogoV1Router.put(
  "/unidades/:id",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Unidad.actualizar
);
catalogoV1Router.delete(
  "/unidades/:id",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Unidad.eliminarLogico
);

// ==========================================
// INSTRUMENTOS Y VERSIONES
// ==========================================
catalogoV1Router.get(
  "/instrumentos",
  autorizar(PERFILES.COLAB, PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Instrumento.listar
);
catalogoV1Router.get(
  "/instrumentos/:id",
  autorizar(PERFILES.COLAB, PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Instrumento.obtenerPorId
);
catalogoV1Router.post(
  "/instrumentos",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Instrumento.crear
);
catalogoV1Router.put(
  "/instrumentos/:id",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Instrumento.actualizar
);
catalogoV1Router.delete(
  "/instrumentos/:id",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Instrumento.eliminarLogico
);

// Versiones de instrumento
catalogoV1Router.get(
  "/instrumentos/:id/versiones",
  autorizar(PERFILES.COLAB, PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Instrumento.listarVersiones
);
catalogoV1Router.get(
  "/instrumentos/:id/versiones/:version",
  autorizar(PERFILES.COLAB, PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Instrumento.obtenerVersion
);
catalogoV1Router.post(
  "/instrumentos/:id/versiones",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Instrumento.crearVersion
);
catalogoV1Router.put(
  "/instrumentos/:id/versiones/:version",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Instrumento.actualizarVersion
);
catalogoV1Router.delete(
  "/instrumentos/:id/versiones/:version",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Instrumento.eliminarVersionLogico
);

// ==========================================
// REACTIVOS
// ==========================================
catalogoV1Router.get(
  "/reactivos",
  autorizar(PERFILES.COLAB, PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Reactivo.listar
);
catalogoV1Router.get(
  "/reactivos/:id",
  autorizar(PERFILES.COLAB, PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Reactivo.obtenerPorId
);
catalogoV1Router.post(
  "/reactivos",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Reactivo.crear
);
catalogoV1Router.put(
  "/reactivos/:id",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Reactivo.actualizar
);
catalogoV1Router.delete(
  "/reactivos/:id",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Reactivo.eliminarLogico
);

// Reactivos por versión de instrumento
catalogoV1Router.get(
  "/instrumentos/:instrumento_id/versiones/:version/reactivos",
  autorizar(PERFILES.COLAB, PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Reactivo.reactivosDeVersion
);
catalogoV1Router.post(
  "/instrumentos/:instrumento_id/versiones/:version/reactivos",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Reactivo.asociarAVersion
);
catalogoV1Router.delete(
  "/instrumentos/:instrumento_id/versiones/:version/reactivos/:reactivo_id",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Reactivo.desasociarDeVersion
);

// ==========================================
// CAMPAÑAS
// ==========================================
catalogoV1Router.get(
  "/campanias",
  autorizar(PERFILES.COLAB, PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Campania.listar
);
catalogoV1Router.get(
  "/campanias/:id",
  autorizar(PERFILES.COLAB, PERFILES.LIDER_TURNO, PERFILES.AUDITOR, PERFILES.ADMIN_SISTEMA),
  Campania.obtenerPorId
);
catalogoV1Router.post(
  "/campanias",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Campania.crear
);
catalogoV1Router.put(
  "/campanias/:id",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Campania.actualizar
);
catalogoV1Router.delete(
  "/campanias/:id",
  autorizar(PERFILES.ADMIN_SISTEMA),
  Campania.eliminarLogico
);
