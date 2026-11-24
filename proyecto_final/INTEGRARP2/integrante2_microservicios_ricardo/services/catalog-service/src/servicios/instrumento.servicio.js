import * as db from "../modelos/catalogo.db.js";
import {
  construirClaveCache,
  leerCache,
  guardarCache,
  invalidarCacheRecurso,
} from "../utilidades/cache.js";
import { HttpError } from "../utilidades/pg-errores.js";

const TIPOS_VALIDOS = new Set(["NOM035", "CLIMA", "BREVE", "PERSONALIZADO"]);

export async function listarInstrumentos(query = {}) {
  const params = {
    activo: query.activo,
    tipo: query.tipo,
    nombre: query.nombre,
    page: query.page || 1,
    limit: query.limit || 10,
  };

  const claveCache = construirClaveCache("instrumentos", params);
  const cacheHit = await leerCache(claveCache);
  if (cacheHit) {
    return { ...cacheHit, _cache: "HIT" };
  }

  const resultado = await db.dbListarInstrumentos(params);
  await guardarCache(claveCache, resultado);
  return { ...resultado, _cache: "MISS" };
}

export async function obtenerInstrumentoPorId(id) {
  const instrumento = await db.dbObtenerInstrumentoPorId(id);
  if (!instrumento) {
    throw new HttpError(404, "NO_ENCONTRADO", `Instrumento '${id}' no encontrado`);
  }
  return instrumento;
}

export async function crearInstrumento(datos) {
  if (!datos.instrumento_id || !datos.nombre || !datos.tipo) {
    throw new HttpError(
      422,
      "CAMPOS_REQUERIDOS",
      "Los campos 'instrumento_id', 'nombre' y 'tipo' son obligatorios"
    );
  }
  if (!TIPOS_VALIDOS.has(datos.tipo)) {
    throw new HttpError(
      422,
      "TIPO_INVALIDO",
      `El tipo '${datos.tipo}' no es válido. Debe ser uno de: ${[...TIPOS_VALIDOS].join(", ")}`
    );
  }
  const creado = await db.dbCrearInstrumento(datos);
  await invalidarCacheRecurso("instrumentos");
  return creado;
}

export async function actualizarInstrumento(id, datos) {
  const existente = await db.dbObtenerInstrumentoPorId(id);
  if (!existente) {
    throw new HttpError(404, "NO_ENCONTRADO", `Instrumento '${id}' no encontrado`);
  }
  if (datos.tipo && !TIPOS_VALIDOS.has(datos.tipo)) {
    throw new HttpError(
      422,
      "TIPO_INVALIDO",
      `El tipo '${datos.tipo}' no es válido. Debe ser uno de: ${[...TIPOS_VALIDOS].join(", ")}`
    );
  }
  const actualizado = await db.dbActualizarInstrumento(id, datos);
  await invalidarCacheRecurso("instrumentos");
  return actualizado;
}

export async function eliminarInstrumentoLogico(id) {
  const existente = await db.dbObtenerInstrumentoPorId(id);
  if (!existente) {
    throw new HttpError(404, "NO_ENCONTRADO", `Instrumento '${id}' no encontrado`);
  }
  const eliminado = await db.dbEliminarInstrumentoLogico(id);
  await invalidarCacheRecurso("instrumentos");
  return eliminado;
}

// ----------------------------------------------------------------------------
// Versiones
// ----------------------------------------------------------------------------

export async function listarVersiones(instrumento_id, query = {}) {
  await obtenerInstrumentoPorId(instrumento_id);
  return db.dbListarVersiones(instrumento_id, query);
}

export async function obtenerVersion(instrumento_id, version) {
  await obtenerInstrumentoPorId(instrumento_id);
  const v = await db.dbObtenerVersion(instrumento_id, version);
  if (!v) {
    throw new HttpError(
      404,
      "NO_ENCONTRADO",
      `Versión ${version} para instrumento '${instrumento_id}' no encontrada`
    );
  }
  return v;
}

export async function crearVersion(instrumento_id, datos) {
  await obtenerInstrumentoPorId(instrumento_id);
  if (datos.version === undefined || !datos.fecha_vigencia_desde) {
    throw new HttpError(
      422,
      "CAMPOS_REQUERIDOS",
      "Los campos 'version' y 'fecha_vigencia_desde' son obligatorios"
    );
  }
  if (Number(datos.version) <= 0) {
    throw new HttpError(422, "VERSION_INVALIDA", "La versión debe ser mayor a 0");
  }
  const creada = await db.dbCrearVersion({
    ...datos,
    instrumento_id,
  });
  await invalidarCacheRecurso("instrumentos");
  return creada;
}

export async function actualizarVersion(instrumento_id, version, datos) {
  await obtenerVersion(instrumento_id, version);
  const actualizada = await db.dbActualizarVersion(instrumento_id, version, datos);
  await invalidarCacheRecurso("instrumentos");
  return actualizada;
}

export async function eliminarVersionLogica(instrumento_id, version) {
  await obtenerVersion(instrumento_id, version);
  const eliminada = await db.dbEliminarVersionLogica(instrumento_id, version);
  await invalidarCacheRecurso("instrumentos");
  return eliminada;
}
