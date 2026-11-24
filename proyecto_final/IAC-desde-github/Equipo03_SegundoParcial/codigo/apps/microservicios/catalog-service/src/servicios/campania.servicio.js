import * as db from "../modelos/catalogo.db.js";
import {
  construirClaveCache,
  leerCache,
  guardarCache,
  invalidarCacheRecurso,
} from "../utilidades/cache.js";
import { HttpError } from "../utilidades/pg-errores.js";

export async function listarCampanias(actor, query = {}) {
  let unidadFiltro = query.unidad_organizacional_id;

  // Acotamiento por perfil: quien no administra ni audita solo ve las
  // campanias de su propia unidad. El filtro NO se toma del cliente: un
  // lider que pidiera otra unidad veria campanias que no le corresponden.
  const esAdminOAuditor =
    actor?.perfil === "ADMINISTRADOR" || actor?.perfil === "AUDITOR" ||
    actor?.perfil === "ESPECIALISTA";

  if (!esAdminOAuditor && actor?.unidad_organizacional_id) {
    unidadFiltro = actor.unidad_organizacional_id;
  }

  const params = {
    estado: query.estado,
    instrumento_id: query.instrumento_id,
    unidad_organizacional_id: unidadFiltro,
    page: query.page || 1,
    limit: query.limit || 10,
    perfil: actor?.perfil || "ANON",
  };

  const claveCache = construirClaveCache("campanias", params);
  const cacheHit = await leerCache(claveCache);
  if (cacheHit) {
    return { ...cacheHit, _cache: "HIT" };
  }

  const resultado = await db.dbListarCampanias(params);
  await guardarCache(claveCache, resultado);
  return { ...resultado, _cache: "MISS" };
}

export async function obtenerCampaniaPorId(id) {
  const campania = await db.dbObtenerCampaniaPorId(id);
  if (!campania) {
    throw new HttpError(404, "NO_ENCONTRADO", `Campaña '${id}' no encontrada`);
  }
  return campania;
}

export async function crearCampania(datos) {
  if (
    !datos.campania_id ||
    !datos.nombre ||
    !datos.fecha_inicio ||
    !datos.fecha_fin ||
    !datos.instrumento_id ||
    datos.version_instrumento === undefined
  ) {
    throw new HttpError(
      422,
      "CAMPOS_REQUERIDOS",
      "Los campos 'campania_id', 'nombre', 'fecha_inicio', 'fecha_fin', 'instrumento_id' y 'version_instrumento' son obligatorios"
    );
  }

  if (new Date(datos.fecha_fin) < new Date(datos.fecha_inicio)) {
    throw new HttpError(
      422,
      "FECHAS_INVALIDAS",
      "La fecha_fin no puede ser anterior a la fecha_inicio"
    );
  }

  const ESTADOS = new Set(["BORRADOR", "ABIERTA", "CERRADA", "CANCELADA"]);
  if (datos.estado !== undefined && !ESTADOS.has(datos.estado)) {
    throw new HttpError(422, "ESTADO_INVALIDO",
      `El estado '${datos.estado}' no es valido. Debe ser uno de: ${[...ESTADOS].join(", ")}`);
  }

  const creada = await db.dbCrearCampania(datos);
  await invalidarCacheRecurso("campanias");
  return creada;
}

export async function actualizarCampania(id, datos) {
  const existente = await db.dbObtenerCampaniaPorId(id);
  if (!existente) {
    throw new HttpError(404, "NO_ENCONTRADO", `Campaña '${id}' no encontrada`);
  }

  const fInicio = datos.fecha_inicio || existente.fecha_inicio;
  const fFin = datos.fecha_fin || existente.fecha_fin;
  if (new Date(fFin) < new Date(fInicio)) {
    throw new HttpError(
      422,
      "FECHAS_INVALIDAS",
      "La fecha_fin no puede ser anterior a la fecha_inicio"
    );
  }

  const ESTADOS = new Set(["BORRADOR", "ABIERTA", "CERRADA", "CANCELADA"]);
  if (datos.estado !== undefined && !ESTADOS.has(datos.estado)) {
    throw new HttpError(422, "ESTADO_INVALIDO",
      `El estado '${datos.estado}' no es valido. Debe ser uno de: ${[...ESTADOS].join(", ")}`);
  }
  // Una campania cerrada no se reabre: sus agregados ya se publicaron con
  // el presupuesto de privacidad consumido y admitir respuestas nuevas
  // cambiaria un resultado ya entregado.
  if (existente.estado === "CERRADA" && datos.estado === "ABIERTA") {
    throw new HttpError(409, "TRANSICION_NO_PERMITIDA",
      "Una campania cerrada no puede reabrirse.");
  }

  const actualizada = await db.dbActualizarCampania(id, datos);
  await invalidarCacheRecurso("campanias");
  return actualizada;
}

export async function eliminarCampaniaLogica(id) {
  const existente = await db.dbObtenerCampaniaPorId(id);
  if (!existente) {
    throw new HttpError(404, "NO_ENCONTRADO", `Campaña '${id}' no encontrada`);
  }
  const eliminada = await db.dbEliminarCampaniaLogica(id);
  if (!eliminada) {
    throw new HttpError(409, "TRANSICION_NO_PERMITIDA",
      `La campania '${id}' esta en estado ${existente.estado} y ya no puede cancelarse.`);
  }
  await invalidarCacheRecurso("campanias");
  return eliminada;
}
