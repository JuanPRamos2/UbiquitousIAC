/**
 * Bitacora operativa en MongoDB.
 *
 * No sustituye a auditoria.evento_auditoria de PostgreSQL, que es la
 * bitacora legal y vive en una tabla a la que la aplicacion solo puede
 * agregar. Esta otra guarda el detalle operativo de alto volumen (una
 * entrada por peticion) que seria caro escribir en la base relacional y
 * que se consulta por correlacion cuando hay que reconstruir una
 * operacion que atraveso varios servicios.
 */
import { base, verificarSinIdentidad } from "../mongo.js";
import { tuberiaBitacoraPorAccion } from "./pipelinesMongo.js";

export const COLECCION = "bitacora_auditoria";

function coleccion(col) {
  return col || base().collection(COLECCION);
}

export async function registrar(entrada, col) {
  const doc = {
    accion: entrada.accion,
    actor_id: entrada.actor_id || null,
    recurso: entrada.recurso || null,
    resultado: entrada.resultado || "EXITO",
    correlacion_id: entrada.correlacion_id || "",
    detalle: entrada.detalle || {},
    timestamp: new Date(),
  };
  verificarSinIdentidad(doc);
  await coleccion(col).insertOne(doc);
  return doc;
}

export async function buscarPorCorrelacion(correlacion_id, col) {
  return coleccion(col)
    .find({ correlacion_id }, { projection: { _id: 0 } })
    .sort({ timestamp: 1 })
    .toArray();
}

export async function contarPorAccion(filtros = {}, col) {
  return coleccion(col).aggregate(tuberiaBitacoraPorAccion(filtros)).toArray();
}
