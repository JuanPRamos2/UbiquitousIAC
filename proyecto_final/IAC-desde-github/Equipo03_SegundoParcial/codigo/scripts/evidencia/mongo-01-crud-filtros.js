// mongosh "$MONGO_URI" scripts/evidencia/mongo-01-crud-filtros.js
// Evidencia: inserción, consulta, actualización con historial[], filtrado e índices.//
// CORRECCIONES respecto a la version original del Integrante 2:
//   * La base se toma de MONGO_BASE (por omision "bienestar"); la version
//     original escribia en "bienestar_nexum", que ningun servicio abre, de
//     modo que la evidencia se generaba en una base vacia y aparte.
//   * El campo de fecha de una respuesta es "fecha", no "fecha_respuesta":
//     con el nombre equivocado el $match no casaba nada y la agregacion
//     salia vacia, lo que se confunde con "no hay datos".
const nombreBase = process.env.MONGO_BASE || "bienestar";
db = db.getSiblingDB(nombreBase);
const seud = "evidencia-seud-" + Date.now();

const ins = db.solicitudes_apoyo.insertOne({ seudonimo_id: seud, mensaje: "Evidencia", fecha: new Date(), estado: "ABIERTA" });
printjson({ insertado: ins.insertedId });

db.solicitudes_apoyo.updateOne(
  { _id: ins.insertedId },
  { $set: { estado: "EN_PROCESO", fecha_actualizacion: new Date() },
    $push: { historial: { estado: "EN_PROCESO", actor_id: "evidencia", fecha: new Date() } } }
);
printjson(db.solicitudes_apoyo.findOne({ _id: ins.insertedId }, { seudonimo_id: 0 }));

print("-- filtrado por estado + orden");
printjson(db.solicitudes_apoyo.find({ estado: "EN_PROCESO" }, { seudonimo_id: 0 }).sort({ fecha: -1 }).limit(5).toArray());

print("-- recuperación por seudónimo (usa ix_sol_seudonimo_fecha)");
printjson(db.solicitudes_apoyo.find({ seudonimo_id: seud }).explain("queryPlanner").queryPlanner.winningPlan);

const corr = "evidencia-corr-" + Date.now();
db.eventos_proceso.insertOne({ seudonimo_id: seud, correlacion_id: corr, tipo: "SOLICITUD_CREADA", timestamp: new Date() });
print("-- eventos por correlación");
printjson(db.eventos_proceso.find({ correlacion_id: corr }).toArray());
print("-- índices");
printjson(db.solicitudes_apoyo.getIndexes());
printjson(db.eventos_proceso.getIndexes());

db.solicitudes_apoyo.deleteOne({ _id: ins.insertedId });
db.eventos_proceso.deleteMany({ correlacion_id: corr });
