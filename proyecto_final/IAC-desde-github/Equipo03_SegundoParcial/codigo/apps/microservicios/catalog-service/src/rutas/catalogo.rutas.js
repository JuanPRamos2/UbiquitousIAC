/**
 * Rutas versionadas de catalog-service: /api/v1/catalogos/...
 *
 * La autorizacion se expresa con PERMISOS y no con perfiles. La diferencia
 * importa: el dia que el equipo cree un perfil nuevo ("coordinador de
 * turno"), basta con asignarle los permisos que le corresponden en la
 * tabla usuarios.perfil_permiso y estas rutas lo aceptan sin recompilar
 * nada. Si la lista fuera de perfiles, habria que editar este archivo y
 * volver a desplegar el servicio.
 *
 * Lectura: la necesitan los cinco perfiles, cada uno por un motivo
 * distinto (el colaborador para ver los reactivos que va a responder, el
 * lider y el especialista para interpretar un agregado, el auditor para
 * revisar que instrumento se aplico, el administrador para operar).
 * Escritura: solo quien administra ese catalogo en concreto.
 */
import { Router } from "express";

import { autenticar } from "@bienestar/comun/autenticacion.js";
import { autorizar } from "@bienestar/comun/autorizacion.js";
import { PERMISOS } from "@bienestar/comun/catalogos-auditoria.js";
import { limiteConsumo } from "@bienestar/comun/servicio.js";

import * as Campania from "../controladores/campania.controlador.js";
import * as Instrumento from "../controladores/instrumento.controlador.js";
import * as Reactivo from "../controladores/reactivo.controlador.js";
import * as Unidad from "../controladores/unidad.controlador.js";

export const catalogoV1Router = Router();

/** Cualquiera de estos permisos habilita la LECTURA del catalogo. */
const LEER = [
  PERMISOS.AUTOREPORTE_RESPONDER,
  PERMISOS.AGREGADO_UNIDAD,
  PERMISOS.AGREGADO_GLOBAL,
  PERMISOS.INSTRUMENTO_ADMIN,
  PERMISOS.CAMPANIA_ADMIN,
  PERMISOS.BITACORA_CONSULTAR,
  PERMISOS.UNIDAD_ADMIN,
];

const leer = () => autorizar(...LEER);

// Autenticacion y limite de consumo para TODO el router: un token valido
// es condicion necesaria incluso para leer un catalogo, porque el catalogo
// revela la estructura organizacional de la empresa.
catalogoV1Router.use(autenticar);
catalogoV1Router.use(limiteConsumo(240, 60));

// ------------------------------------------------ unidades organizacionales
catalogoV1Router.get("/unidades", leer(), Unidad.listar);
catalogoV1Router.get("/unidades/:id", leer(), Unidad.obtenerPorId);
catalogoV1Router.post("/unidades", autorizar(PERMISOS.UNIDAD_ADMIN), Unidad.crear);
catalogoV1Router.put("/unidades/:id", autorizar(PERMISOS.UNIDAD_ADMIN), Unidad.actualizar);
catalogoV1Router.delete("/unidades/:id", autorizar(PERMISOS.UNIDAD_ADMIN), Unidad.eliminarLogico);

// ----------------------------------------------- instrumentos y versiones
catalogoV1Router.get("/instrumentos", leer(), Instrumento.listar);
catalogoV1Router.get("/instrumentos/:id", leer(), Instrumento.obtenerPorId);
catalogoV1Router.post("/instrumentos", autorizar(PERMISOS.INSTRUMENTO_ADMIN), Instrumento.crear);
catalogoV1Router.put("/instrumentos/:id", autorizar(PERMISOS.INSTRUMENTO_ADMIN), Instrumento.actualizar);
catalogoV1Router.delete("/instrumentos/:id", autorizar(PERMISOS.INSTRUMENTO_ADMIN), Instrumento.eliminarLogico);

catalogoV1Router.get("/instrumentos/:id/versiones", leer(), Instrumento.listarVersiones);
catalogoV1Router.get("/instrumentos/:id/versiones/:version", leer(), Instrumento.obtenerVersion);
catalogoV1Router.post("/instrumentos/:id/versiones", autorizar(PERMISOS.INSTRUMENTO_ADMIN), Instrumento.crearVersion);
catalogoV1Router.put("/instrumentos/:id/versiones/:version", autorizar(PERMISOS.INSTRUMENTO_ADMIN), Instrumento.actualizarVersion);
catalogoV1Router.delete("/instrumentos/:id/versiones/:version", autorizar(PERMISOS.INSTRUMENTO_ADMIN), Instrumento.eliminarVersionLogico);

// ------------------------------------------------------------- reactivos
catalogoV1Router.get("/reactivos", leer(), Reactivo.listar);
catalogoV1Router.get("/reactivos/:id", leer(), Reactivo.obtenerPorId);
catalogoV1Router.post("/reactivos", autorizar(PERMISOS.INSTRUMENTO_ADMIN), Reactivo.crear);
catalogoV1Router.put("/reactivos/:id", autorizar(PERMISOS.INSTRUMENTO_ADMIN), Reactivo.actualizar);
catalogoV1Router.delete("/reactivos/:id", autorizar(PERMISOS.INSTRUMENTO_ADMIN), Reactivo.eliminarLogico);

catalogoV1Router.get("/instrumentos/:instrumento_id/versiones/:version/reactivos",
  leer(), Reactivo.reactivosDeVersion);
catalogoV1Router.post("/instrumentos/:instrumento_id/versiones/:version/reactivos",
  autorizar(PERMISOS.INSTRUMENTO_ADMIN), Reactivo.asociarAVersion);
catalogoV1Router.delete("/instrumentos/:instrumento_id/versiones/:version/reactivos/:reactivo_id",
  autorizar(PERMISOS.INSTRUMENTO_ADMIN), Reactivo.desasociarDeVersion);

// -------------------------------------------------------------- campanias
catalogoV1Router.get("/campanias", leer(), Campania.listar);
catalogoV1Router.get("/campanias/:id", leer(), Campania.obtenerPorId);
catalogoV1Router.post("/campanias", autorizar(PERMISOS.CAMPANIA_ADMIN), Campania.crear);
catalogoV1Router.put("/campanias/:id", autorizar(PERMISOS.CAMPANIA_ADMIN), Campania.actualizar);
catalogoV1Router.delete("/campanias/:id", autorizar(PERMISOS.CAMPANIA_ADMIN), Campania.eliminarLogico);

// ------------------------------------------- catalogos de apoyo (lectura)
catalogoV1Router.get("/dimensiones", leer(), Instrumento.listarDimensiones);
catalogoV1Router.get("/fuentes", leer(), Instrumento.listarFuentes);
catalogoV1Router.get("/parametros", leer(), Instrumento.listarParametros);
