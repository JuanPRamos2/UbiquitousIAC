import { mongoDb, conectarMongo } from "../config/mongo.js";

export async function crearSolicitud({ seudonimo_id, mensaje }) {
  await conectarMongo();
  const doc = {
    seudonimo_id,
    mensaje,
    fecha: new Date(),
    estado: "ABIERTA",
  };
  const r = await mongoDb().collection("solicitudes_apoyo").insertOne(doc);
  return { id: String(r.insertedId), fecha: doc.fecha };
}

export async function listarSolicitudes({ limite = 50 } = {}) {
  await conectarMongo();
  return mongoDb()
    .collection("solicitudes_apoyo")
    .find({}, { projection: { seudonimo_id: 0 } })
    .sort({ fecha: -1 })
    .limit(Math.min(Number(limite) || 50, 200))
    .toArray();
}
