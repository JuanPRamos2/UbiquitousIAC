/**
 * Solicitudes de apoyo, en MongoDB.
 *
 * Una solicitud de apoyo es el unico lugar del sistema donde una persona
 * pide ayuda de forma individual, y por eso es el mas delicado: se guarda
 * contra el seudonimo y nunca contra el empleado. Quien atiende la
 * solicitud ve un seudonimo y un texto; para contactar a la persona debe
 * pasar por el proceso documentado de reidentificacion, que queda en la
 * bitacora.
 *
 * El historial se agrega con $push y nunca se reescribe: el ciclo de vida
 * de una solicitud es evidencia y se audita.
 */
import { randomUUID } from "node:crypto";

import { base, verificarSinIdentidad } from "../mongo.js";

export const COLECCION = "solicitudes_apoyo";
export const ESTADOS_SOLICITUD = ["ABIERTA", "EN_PROCESO", "CERRADA"];

/** Transiciones permitidas. Una solicitud cerrada no vuelve a abrirse. */
export const TRANSICIONES = {
  ABIERTA: ["EN_PROCESO", "CERRADA"],
  EN_PROCESO: ["CERRADA"],
  CERRADA: [],
};

function coleccion(col) {
  return col || base().collection(COLECCION);
}

export function normalizarSolicitud(doc) {
  if (!doc) return null;
  return {
    id: doc.id || doc.id_publico,
    seudonimo_id: doc.seudonimo_id,
    mensaje: doc.mensaje,
    fecha: doc.fecha,
    estado: doc.estado,
    fecha_actualizacion: doc.fecha_actualizacion || null,
    historial: doc.historial || [],
  };
}

export async function crearSolicitud({ seudonimo_id, mensaje, correlacion_id }, col) {
  const ahora = new Date();
  // Identificador propio y no el _id de MongoDB: el _id es un detalle de
  // la base y no debe aparecer en el contrato de la API, porque amarraria
  // el contrato al motor de persistencia.
  const doc = {
    id_publico: `SOL-${randomUUID().replace(/-/g, "").slice(0, 12).toUpperCase()}`,
    seudonimo_id,
    mensaje,
    estado: "ABIERTA",
    fecha: ahora,
    correlacion_id: correlacion_id || "",
    historial: [{ estado: "ABIERTA", fecha: ahora, actor_id: null, nota: "Solicitud creada" }],
  };
  verificarSinIdentidad(doc);
  const r = await coleccion(col).insertOne(doc);
  return normalizarSolicitud({ ...doc, _id: r.insertedId, id: doc.id_publico });
}

/**
 * Cambia el estado y agrega la entrada al historial en UNA sola operacion
 * atomica. La transicion valida va en el filtro, no en un if previo: asi
 * dos auditores que cierren la misma solicitud a la vez no producen dos
 * entradas de historial contradictorias.
 */
export async function actualizarEstadoSolicitud({ id, estado, actor_id, nota }, col) {
  const permitidos = Object.entries(TRANSICIONES)
    .filter(([, destinos]) => destinos.includes(estado))
    .map(([origen]) => origen);
  if (permitidos.length === 0) return null;

  const r = await coleccion(col).findOneAndUpdate(
    { id_publico: id, estado: { $in: permitidos } },
    {
      $set: { estado, fecha_actualizacion: new Date() },
      $push: {
        historial: {
          estado, fecha: new Date(),
          actor_id: actor_id || null,
          nota: nota || null,
        },
      },
    },
    { returnDocument: "after", projection: { _id: 0 } }
  );
  const doc = r?.value ?? r ?? null;
  return normalizarSolicitud(doc);
}

export async function listarSolicitudes({ estado, seudonimo_id, limite = 50, pagina = 1 } = {}, col) {
  const filtro = {};
  if (estado) filtro.estado = estado;
  if (seudonimo_id) filtro.seudonimo_id = seudonimo_id;
  const lim = Math.min(Math.max(Number(limite) || 50, 1), 100);
  const pag = Math.max(Number(pagina) || 1, 1);
  const docs = await coleccion(col)
    .find(filtro, { projection: { _id: 0 } })
    .sort({ fecha: -1 })
    .skip((pag - 1) * lim)
    .limit(lim)
    .toArray();
  return docs.map(normalizarSolicitud);
}

export async function contarSolicitudes(filtro = {}, col) {
  return coleccion(col).countDocuments(filtro);
}

export async function obtenerSolicitud(id, col) {
  const doc = await coleccion(col).findOne({ id_publico: id }, { projection: { _id: 0 } });
  return normalizarSolicitud(doc);
}
