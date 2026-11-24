import * as sql from "../sql/reportes.sql.js";

export function crearRepositorio({ query, mongo }) {
  async function filas(definicion) {
    const resultado = await query(definicion.text, definicion.params);
    return resultado.rows;
  }

  async function uno(definicion) {
    const resultado = await query(definicion.text, definicion.params);
    return resultado.rows[0] || null;
  }

  return {
    conteos: (unidadId) => uno(sql.sqlConteosGenerales(unidadId)),
    campaniasPorEstado: () => filas(sql.sqlCampaniasPorEstado()),
    intervencionesPorEstado: (unidadId) => filas(sql.sqlIntervencionesPorEstado(unidadId)),
    reglasPorNivel: () => filas(sql.sqlReglasPorNivel()),
    fuentes: () => filas(sql.sqlFuentes()),
    participacion: (unidadId) => filas(sql.sqlParticipacion(unidadId)),
    tendencia: (unidadId, dimensionId) => filas(sql.sqlTendencia(unidadId, dimensionId)),
    umbralK: async () => Number((await uno(sql.sqlUmbralK()))?.k || 5),
    auditoriaPorAccion: (desde, hasta) => filas(sql.sqlAuditoriaPorAccion(desde, hasta)),
    auditoriaPorPeriodo: (desde, hasta) => filas(sql.sqlAuditoriaPorPeriodo(desde, hasta)),
    publicacion: (unidadId) => filas(sql.sqlPublicacion(unidadId)),
    eventosAuditoria: async () => Number((await uno(sql.sqlEventosAuditoria()))?.total || 0),
    async solicitudesPorEstado() {
      const db = await mongo();
      const filasMongo = await db
        .collection("solicitudes_apoyo")
        .aggregate([
          { $group: { _id: { $ifNull: ["$estado", "ABIERTA"] }, total: { $sum: 1 } } },
          { $sort: { _id: 1 } },
        ])
        .toArray();
      return filasMongo.map((fila) => ({ estado: fila._id, total: fila.total }));
    },
  };
}
