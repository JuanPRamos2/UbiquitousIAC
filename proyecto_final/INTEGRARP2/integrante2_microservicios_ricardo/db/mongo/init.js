db = db.getSiblingDB("bienestar_nexum");

db.respuestas_encuesta.createIndex(
  { seudonimo_id: 1, campania_id: 1 },
  { unique: true, name: "ux_seudonimo_campania" }
);
db.respuestas_encuesta.createIndex({ unidad_organizacional_id: 1, campania_id: 1 });

db.bitacora_auditoria.createIndex({ timestamp: -1 });
db.bitacora_auditoria.createIndex({ correlacion_id: 1 });
db.bitacora_auditoria.createIndex({ actor_id: 1, timestamp: -1 });


// ---- Fase 1 Integrante 2 (idempotente: createIndex con mismo nombre/spec no falla) ----
db.solicitudes_apoyo.createIndex({ seudonimo_id: 1, fecha: -1 }, { name: "ix_sol_seudonimo_fecha" });
db.solicitudes_apoyo.createIndex({ estado: 1, fecha: -1 }, { name: "ix_sol_estado_fecha" });

const estadosSolicitud = ["ABIERTA", "EN_PROCESO", "CERRADA"];
const validadorEventos = {
  $jsonSchema: {
    bsonType: "object",
    required: ["seudonimo_id", "correlacion_id", "tipo", "timestamp"],
    properties: {
      seudonimo_id: { bsonType: "string" },
      correlacion_id: { bsonType: "string" },
      tipo: { bsonType: "string" },
      timestamp: { bsonType: "date" },
      detalle: { bsonType: "object" },
    },
    additionalProperties: true,
  },
};
if (!db.getCollectionNames().includes("eventos_proceso")) {
  db.createCollection("eventos_proceso", { validator: validadorEventos, validationAction: "error" });
} else {
  db.runCommand({ collMod: "eventos_proceso", validator: validadorEventos });
}
db.eventos_proceso.createIndex({ seudonimo_id: 1, timestamp: -1 }, { name: "ix_evt_seudonimo_ts" });
db.eventos_proceso.createIndex({ correlacion_id: 1 }, { name: "ix_evt_correlacion" });
db.eventos_proceso.createIndex({ tipo: 1, timestamp: -1 }, { name: "ix_evt_tipo_ts" });
