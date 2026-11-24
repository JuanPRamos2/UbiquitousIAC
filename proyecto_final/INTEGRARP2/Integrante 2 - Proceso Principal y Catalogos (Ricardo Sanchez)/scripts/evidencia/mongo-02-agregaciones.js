// mongosh bienestar_nexum scripts/evidencia/mongo-02-agregaciones.js
// Evidencia: aggregate() de respuestas por unidad/campaña/rango y conteo de bitácora por acción.
db = db.getSiblingDB("bienestar_nexum");
const desde = new Date("2000-01-01");
const hasta = new Date("2100-01-01");

print("-- respuestas por unidad y campaña");
printjson(db.respuestas_encuesta.aggregate([
  { $match: { fecha_respuesta: { $gte: desde, $lt: hasta } } },
  { $group: { _id: { unidad_organizacional_id: "$unidad_organizacional_id", campania_id: "$campania_id" }, total: { $sum: 1 } } },
  { $project: { _id: 0, unidad_organizacional_id: "$_id.unidad_organizacional_id", campania_id: "$_id.campania_id", total: 1 } },
  { $sort: { campania_id: 1, unidad_organizacional_id: 1 } },
]).toArray());

print("-- bitácora: conteo por acción/resultado");
printjson(db.bitacora_auditoria.aggregate([
  { $match: { timestamp: { $gte: desde, $lt: hasta } } },
  { $group: { _id: { accion: "$accion", resultado: "$resultado" }, total: { $sum: 1 } } },
  { $project: { _id: 0, accion: "$_id.accion", resultado: "$_id.resultado", total: 1 } },
  { $sort: { total: -1, accion: 1 } },
]).toArray());

print("-- solicitudes por estado");
printjson(db.solicitudes_apoyo.aggregate([{ $group: { _id: "$estado", total: { $sum: 1 } } }]).toArray());
