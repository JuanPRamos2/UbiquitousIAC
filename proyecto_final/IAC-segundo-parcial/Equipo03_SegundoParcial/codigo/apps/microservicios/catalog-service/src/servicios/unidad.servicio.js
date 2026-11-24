import * as db from "../modelos/catalogo.db.js";
import {
  construirClaveCache,
  leerCache,
  guardarCache,
  invalidarCacheRecurso,
} from "../utilidades/cache.js";
import { HttpError } from "../utilidades/pg-errores.js";

export async function listarUnidades(actor, query = {}) {
  const params = {
    activa: query.activa,
    nombre: query.nombre,
    unidad_padre_id: query.unidad_padre_id,
    page: query.page || 1,
    limit: query.limit || 10,
    perfil: actor?.perfil || "ANON",
  };

  const claveCache = construirClaveCache("unidades", params);
  const cacheHit = await leerCache(claveCache);
  if (cacheHit) {
    return { ...cacheHit, _cache: "HIT" };
  }

  const resultado = await db.dbListarUnidades(params);
  await guardarCache(claveCache, resultado);
  return { ...resultado, _cache: "MISS" };
}

export async function obtenerUnidadPorId(id) {
  const unidad = await db.dbObtenerUnidadPorId(id);
  if (!unidad) {
    throw new HttpError(404, "NO_ENCONTRADO", `Unidad organizacional '${id}' no encontrada`);
  }
  return unidad;
}

/**
 * Comprueba que los campos numericos sean numeros ANTES de ir a PostgreSQL.
 *
 * Sin esto, `plantilla_declarada: "siete"` pasaba por Number(), llegaba a
 * la base como NaN y el cliente recibia un 500 con el texto
 * `invalid input syntax for type integer: "NaN"`. Dos cosas mal: un error
 * del cliente contado como fallo del servidor, y un mensaje de PostgreSQL
 * expuesto hacia afuera. El fallo se descubrio al mandar el cuerpo en XML,
 * donde los valores llegan siempre como cadenas, pero existia igual en
 * JSON: bastaba mandar el numero entre comillas.
 */
function validarEnteros(datos, campos) {
  for (const campo of campos) {
    const valor = datos[campo];
    if (valor === undefined || valor === null || valor === "") continue;
    const n = Number(valor);
    if (!Number.isInteger(n) || n < 0) {
      throw new HttpError(422, "VALIDACION",
        `El campo '${campo}' tiene que ser un entero mayor o igual a cero; ` +
        `llego '${valor}'.`);
    }
  }
}

export async function crearUnidad(datos) {
  if (!datos.unidad_organizacional_id || !datos.nombre) {
    throw new HttpError(
      422,
      "CAMPOS_REQUERIDOS",
      "Los campos 'unidad_organizacional_id' y 'nombre' son obligatorios"
    );
  }
  validarEnteros(datos, ["nivel_jerarquico", "plantilla_declarada"]);
  const creada = await db.dbCrearUnidad(datos);
  await invalidarCacheRecurso("unidades");
  return creada;
}

export async function actualizarUnidad(id, datos) {
  const existente = await db.dbObtenerUnidadPorId(id);
  if (!existente) {
    throw new HttpError(404, "NO_ENCONTRADO", `Unidad organizacional '${id}' no encontrada`);
  }
  validarEnteros(datos, ["nivel_jerarquico", "plantilla_declarada"]);
  const actualizada = await db.dbActualizarUnidad(id, datos);
  await invalidarCacheRecurso("unidades");
  return actualizada;
}

export async function eliminarUnidadLogica(id) {
  const existente = await db.dbObtenerUnidadPorId(id);
  if (!existente) {
    throw new HttpError(404, "NO_ENCONTRADO", `Unidad organizacional '${id}' no encontrada`);
  }
  const eliminada = await db.dbEliminarUnidadLogica(id);
  await invalidarCacheRecurso("unidades");
  return eliminada;
}
