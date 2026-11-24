import * as sql from "../sql/consultas.sql.js";

function escaparRegex(texto) {
  return texto.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function fechaIso(valor) {
  if (!valor) return null;
  if (valor instanceof Date) return valor.toISOString();
  return String(valor);
}

export function crearRepositorio({ query, mongo }) {
  async function listar(definicion) {
    const [filas, conteo] = await Promise.all([
      query(definicion.text, definicion.params),
      query(definicion.countText, definicion.countParams),
    ]);
    return { filas: filas.rows, total: conteo.rows[0].total };
  }

  async function uno(definicion) {
    const resultado = await query(definicion.text, definicion.params);
    return resultado.rows[0] || null;
  }

  return {
    campanias: (filtros) => listar(sql.sqlCampanias(filtros)),
    campaniaPorId: (id) => uno(sql.sqlCampaniaPorId(id)),
    unidades: (filtros) => listar(sql.sqlUnidades(filtros)),
    unidadPorId: (id) => uno(sql.sqlUnidadPorId(id)),
    instrumentos: (filtros) => listar(sql.sqlInstrumentos(filtros)),
    fuentes: (filtros) => listar(sql.sqlFuentes(filtros)),
    intervenciones: (filtros) => listar(sql.sqlIntervenciones(filtros)),
    intervencionPorId: (id) => uno(sql.sqlIntervencionPorId(id)),
    auditoria: (filtros) => listar(sql.sqlAuditoria(filtros)),
    resultados: (filtros) => listar(sql.sqlResultados(filtros)),
    presupuesto: (filtros) => listar(sql.sqlPresupuesto(filtros)),
    participacion: (usuarioId) => uno(sql.sqlParticipacion(usuarioId)),
    async solicitudes(filtros) {
      const db = await mongo();
      const coleccion = db.collection("solicitudes_apoyo");
      const filtro = {};
      if (filtros.estado) filtro.estado = filtros.estado;
      if (filtros.search) filtro.mensaje = { $regex: escaparRegex(filtros.search), $options: "i" };
      const total = await coleccion.countDocuments(filtro);
      const documentos = await coleccion
        .find(filtro, { projection: { seudonimo_id: 0 } })
        .sort({ fecha: -1 })
        .skip(filtros.offset)
        .limit(filtros.limit)
        .toArray();
      return {
        total,
        filas: documentos.map((doc) => ({
          id: String(doc._id),
          fecha: fechaIso(doc.fecha),
          mensaje: doc.mensaje,
          estado: doc.estado || "ABIERTA",
        })),
      };
    },
  };
}
