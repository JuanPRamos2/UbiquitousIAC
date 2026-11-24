/**
 * Eventos del proceso operativo, en MongoDB.
 *
 * Un evento registra QUE paso en el proceso, nunca a quien le paso: la
 * llave es el seudonimo y la coleccion tiene prohibido empleado_id tanto
 * en la capa de acceso (comun/mongo.js) como en el validador
 * $jsonSchema de la propia base (db/mongo/init.js). Dos cercas para la
 * misma regla, porque un servicio futuro escrito por otra persona podria
 * no pasar por la primera.
 */
import { base, verificarSinIdentidad } from "../mongo.js";

export const COLECCION = "eventos_proceso";

function coleccion(col) {
  return col || base().collection(COLECCION);
}

export async function registrarEventoProceso(evento, col) {
  const doc = {
    seudonimo_id: evento.seudonimo_id || null,
    correlacion_id: evento.correlacion_id || "",
    tipo: evento.tipo,
    timestamp: evento.timestamp ? new Date(evento.timestamp) : new Date(),
    detalle: evento.detalle || {},
  };
  // El validador de la base exige seudonimo_id de tipo string: un evento
  // que no pertenece a una persona (por ejemplo el cambio de estado que
  // hace un auditor) se marca explicitamente.
  if (doc.seudonimo_id === null) doc.seudonimo_id = "SIN_SEUDONIMO";
  verificarSinIdentidad(doc);
  const r = await coleccion(col).insertOne(doc);
  return { ...doc, _id: r.insertedId, id: String(r.insertedId) };
}

export async function listarEventosProceso(
  { seudonimo_id, correlacion_id, tipo, limite = 50, pagina = 1 } = {}, col) {
  const filtro = {};
  if (seudonimo_id) filtro.seudonimo_id = seudonimo_id;
  if (correlacion_id) filtro.correlacion_id = correlacion_id;
  if (tipo) filtro.tipo = tipo;
  const lim = Math.min(Math.max(Number(limite) || 50, 1), 100);
  const pag = Math.max(Number(pagina) || 1, 1);
  const cursor = coleccion(col)
    .find(filtro, { projection: { _id: 0 } })
    .sort({ timestamp: -1 })
    .skip((pag - 1) * lim)
    .limit(lim);
  return cursor.toArray();
}

export async function contarEventos(filtro = {}, col) {
  return coleccion(col).countDocuments(filtro);
}
