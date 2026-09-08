db = db.getSiblingDB("bienestar_nexum");

db.respuestas_encuesta.createIndex(
  { seudonimo_id: 1, campania_id: 1 },
  { unique: true, name: "ux_seudonimo_campania" }
);
db.respuestas_encuesta.createIndex({ unidad_organizacional_id: 1, campania_id: 1 });

db.bitacora_auditoria.createIndex({ timestamp: -1 });
db.bitacora_auditoria.createIndex({ correlacion_id: 1 });
db.bitacora_auditoria.createIndex({ actor_id: 1, timestamp: -1 });
