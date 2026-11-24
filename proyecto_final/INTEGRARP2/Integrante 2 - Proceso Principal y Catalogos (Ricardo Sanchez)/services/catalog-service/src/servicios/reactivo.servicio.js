import * as db from "../modelos/catalogo.db.js";
import {
  construirClaveCache,
  leerCache,
  guardarCache,
  invalidarCacheRecurso,
} from "../utilidades/cache.js";
import { HttpError } from "../utilidades/pg-errores.js";

export async function listarReactivos(query = {}) {
  const params = {
    activo: query.activo,
    dimension: query.dimension,
    q: query.q || query.search,
    page: query.page || 1,
    limit: query.limit || 10,
  };

  const claveCache = construirClaveCache("reactivos", params);
  const cacheHit = await leerCache(claveCache);
  if (cacheHit) {
    return { ...cacheHit, _cache: "HIT" };
  }

  const resultado = await db.dbListarReactivos(params);
  await guardarCache(claveCache, resultado);
  return { ...resultado, _cache: "MISS" };
}

export async function obtenerReactivoPorId(id) {
  const reactivo = await db.dbObtenerReactivoPorId(id);
  if (!reactivo) {
    throw new HttpError(404, "NO_ENCONTRADO", `Reactivo '${id}' no encontrado`);
  }
  return reactivo;
}

export async function crearReactivo(datos) {
  if (!datos.reactivo_id || !datos.texto) {
    throw new HttpError(
      422,
      "CAMPOS_REQUERIDOS",
      "Los campos 'reactivo_id' y 'texto' son obligatorios"
    );
  }
  if (datos.escala_min !== undefined && datos.escala_max !== undefined) {
    if (Number(datos.escala_min) >= Number(datos.escala_max)) {
      throw new HttpError(
        422,
        "ESCALA_INVALIDA",
        "La escala_min debe ser estrictamente menor que la escala_max"
      );
    }
  }
  const creado = await db.dbCrearReactivo(datos);
  await invalidarCacheRecurso("reactivos");
  return creado;
}

export async function actualizarReactivo(id, datos) {
  const existente = await db.dbObtenerReactivoPorId(id);
  if (!existente) {
    throw new HttpError(404, "NO_ENCONTRADO", `Reactivo '${id}' no encontrado`);
  }
  const min = datos.escala_min !== undefined ? Number(datos.escala_min) : existente.escala_min;
  const max = datos.escala_max !== undefined ? Number(datos.escala_max) : existente.escala_max;
  if (min >= max) {
    throw new HttpError(
      422,
      "ESCALA_INVALIDA",
      "La escala_min debe ser estrictamente menor que la escala_max"
    );
  }
  const actualizado = await db.dbActualizarReactivo(id, datos);
  await invalidarCacheRecurso("reactivos");
  return actualizado;
}

export async function eliminarReactivoLogico(id) {
  const existente = await db.dbObtenerReactivoPorId(id);
  if (!existente) {
    throw new HttpError(404, "NO_ENCONTRADO", `Reactivo '${id}' no encontrado`);
  }
  const eliminado = await db.dbEliminarReactivoLogico(id);
  await invalidarCacheRecurso("reactivos");
  return eliminado;
}

// ----------------------------------------------------------------------------
// Reactivos de versión de instrumento
// ----------------------------------------------------------------------------

export async function reactivosDeVersion(instrumento_id, version) {
  return db.dbListarReactivosDeVersion(instrumento_id, version);
}

export async function asociarAVersion(instrumento_id, version, datos) {
  if (!datos.reactivo_id || datos.orden === undefined) {
    throw new HttpError(
      422,
      "CAMPOS_REQUERIDOS",
      "Los campos 'reactivo_id' y 'orden' son obligatorios"
    );
  }
  if (Number(datos.orden) <= 0) {
    throw new HttpError(422, "ORDEN_INVALIDO", "El orden debe ser mayor a 0");
  }
  const asociacion = await db.dbAsociarReactivoAVersion(instrumento_id, version, datos);
  await invalidarCacheRecurso("reactivos");
  await invalidarCacheRecurso("instrumentos");
  return asociacion;
}

export async function desasociarDeVersion(instrumento_id, version, reactivo_id) {
  const desasociado = await db.dbDesasociarReactivoDeVersion(instrumento_id, version, reactivo_id);
  if (!desasociado) {
    throw new HttpError(
      404,
      "NO_ENCONTRADO",
      `Asociación del reactivo '${reactivo_id}' con versión ${version} no encontrada`
    );
  }
  await invalidarCacheRecurso("reactivos");
  await invalidarCacheRecurso("instrumentos");
  return desasociado;
}
