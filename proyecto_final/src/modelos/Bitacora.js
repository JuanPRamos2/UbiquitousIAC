import { mongoDb, conectarMongo } from "../config/mongo.js";
import { validarCodigosAuditoria } from "./Catalogo.js";

export function colBitacora() {
  return mongoDb().collection("bitacora_auditoria");
}

export async function registrarBitacora(doc) {
  const chequeo = await validarCodigosAuditoria({
    accion: doc.accion,
    recurso: doc.recurso,
    resultado: doc.resultado,
  });
  if (!chequeo.accion_ok || !chequeo.recurso_ok || !chequeo.resultado_ok) {
    throw new Error(
      `Código de auditoría fuera de catálogo PostgreSQL: accion=${doc.accion} recurso=${doc.recurso} resultado=${doc.resultado}`
    );
  }

  await conectarMongo();
  await colBitacora().insertOne({
    actor_id: doc.actor_id,
    actor_perfil: doc.actor_perfil,
    accion: doc.accion,
    recurso: doc.recurso,
    resultado: doc.resultado,
    correlacion_id: doc.correlacion_id,
    timestamp: doc.timestamp || new Date(),
  });
}

export async function listarBitacora({ limite = 50 } = {}) {
  await conectarMongo();
  return colBitacora()
    .find({}, { projection: {} })
    .sort({ timestamp: -1 })
    .limit(Math.min(Number(limite) || 50, 200))
    .toArray();
}

export async function listarBitacoraDeActor(actorId, { limite = 50 } = {}) {
  await conectarMongo();
  return colBitacora()
    .find({ actor_id: actorId })
    .sort({ timestamp: -1 })
    .limit(Math.min(Number(limite) || 50, 200))
    .toArray();
}
