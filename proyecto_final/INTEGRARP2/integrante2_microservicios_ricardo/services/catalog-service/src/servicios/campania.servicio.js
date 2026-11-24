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

  // Scoping por perfil si no es ADMIN_SISTEMA ni AUDITOR
  const esAdminOAuditor =
    actor?.perfil === "ADMIN_SISTEMA" || actor?.perfil === "AUDITOR";

  if (!esAdminOAuditor && actor?.unidad_organizacional_id) {
    unidadFiltro = actor.unidad_organizacional_id;
  }

  const params = {
    activa: query.activa,
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
  await invalidarCacheRecurso("campanias");
  return eliminada;
}
