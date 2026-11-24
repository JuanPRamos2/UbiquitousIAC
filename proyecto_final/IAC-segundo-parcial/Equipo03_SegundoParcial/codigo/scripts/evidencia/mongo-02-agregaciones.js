// mongosh "$MONGO_URI" scripts/evidencia/mongo-02-agregaciones.js
// Evidencia: aggregate() de respuestas por unidad/campaña/rango y conteo de bitácora por acción.//
// CORRECCIONES respecto a la version original del Integrante 2:
//   * La base se toma de MONGO_BASE (por omision "bienestar"); la version
//     original escribia en "bienestar_nexum", que ningun servicio abre, de
//     modo que la evidencia se generaba en una base vacia y aparte.
//   * El campo de fecha de una respuesta es "fecha", no "fecha_respuesta":
//     con el nombre equivocado el $match no casaba nada y la agregacion
//     salia vacia, lo que se confunde con "no hay datos".
const nombreBase = process.env.MONGO_BASE || "bienestar";
db = db.getSiblingDB(nombreBase);
const desde = new Date("2000-01-01");
const hasta = new Date("2100-01-01");

print("-- respuestas por unidad y campaña");
printjson(db.respuestas_encuesta.aggregate([
  { $match: { fecha: { $gte: desde, $lt: hasta } } },
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
