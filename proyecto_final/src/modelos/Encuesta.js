import { mongoDb, conectarMongo } from "../config/mongo.js";

export function colRespuestas() {
  return mongoDb().collection("respuestas_encuesta");
}

export async function insertarRespuesta(doc) {
  await conectarMongo();
  const result = await colRespuestas().insertOne(doc);
  return { ...doc, _id: result.insertedId };
}

export async function existeRespuesta(seudonimoId, campaniaId) {
  await conectarMongo();
  const n = await colRespuestas().countDocuments({
    seudonimo_id: seudonimoId,
    campania_id: campaniaId,
  });
  return n > 0;
}

export async function respuestasPorUnidadCampania(unidadId, campaniaId) {
  await conectarMongo();
  return colRespuestas()
    .find(
      { unidad_organizacional_id: unidadId, campania_id: campaniaId },
      { projection: { seudonimo_id: 0, _id: 0 } }
    )
    .toArray();
}

export async function respuestasDeSeudonimo(seudonimoId) {
  await conectarMongo();
  return colRespuestas()
    .find(
      { seudonimo_id: seudonimoId },
      { projection: { seudonimo_id: 0, _id: 0, unidad_organizacional_id: 0 } }
    )
    .sort({ fecha_respuesta: -1 })
    .limit(12)
    .toArray();
}
