import { pgQuery, pgTransaction } from "../config/postgres.js";

export async function insertarRespuesta({
  seudonimo_id,
  campania_id,
  unidad_organizacional_id,
  aviso_id,
  respuestas,
}) {
  return pgTransaction(async (query) => {
    const cabeza = await query(
      `INSERT INTO autoreporte.respuesta
         (seudonimo_id, campania_id, unidad_organizacional_id, aviso_id)
       VALUES ($1, $2, $3, $4)
       RETURNING respuesta_id, fecha_respuesta`,
      [seudonimo_id, campania_id, unidad_organizacional_id, aviso_id]
    );
    const respuestaId = cabeza.rows[0].respuesta_id;
    for (const item of respuestas) {
      await query(
        `INSERT INTO autoreporte.respuesta_detalle (respuesta_id, reactivo_id, valor)
         VALUES ($1, $2, $3)`,
        [respuestaId, item.reactivo_id, item.valor]
      );
    }
    return {
      respuesta_id: respuestaId,
      fecha_respuesta: cabeza.rows[0].fecha_respuesta,
    };
  });
}

export async function existeRespuesta(seudonimoId, campaniaId) {
  const r = await pgQuery(
    `SELECT 1 FROM autoreporte.respuesta
     WHERE seudonimo_id = $1 AND campania_id = $2`,
    [seudonimoId, campaniaId]
  );
  return r.rowCount > 0;
}

export async function respuestasDeSeudonimo(seudonimoId) {
  const r = await pgQuery(
    `SELECT campania_id, fecha_respuesta
     FROM autoreporte.respuesta
     WHERE seudonimo_id = $1
     ORDER BY fecha_respuesta DESC
     LIMIT 12`,
    [seudonimoId]
  );
  return r.rows;
}
