export function sqlConteosGenerales(unidadId) {
  const params = [];
  const intervencion = unidadId
    ? (params.push(unidadId), "WHERE unidad_organizacional_id = $1")
    : "";
  const publicacion = unidadId ? "WHERE unidad_organizacional_id = $1" : "";
  return {
    text: `SELECT
             (SELECT COUNT(*)::int FROM catalogo.campania) AS campanias,
             (SELECT COUNT(*)::int FROM organizacion.unidad_organizacional WHERE activa) AS unidades,
             (SELECT COUNT(*)::int FROM intervencion.plan ${intervencion}) AS intervenciones,
             (SELECT COUNT(*)::int FROM agregado.resultado_protegido ${publicacion}) AS resultados`,
    params,
  };
}

export function sqlCampaniasPorEstado() {
  return {
    text: `SELECT estado, COUNT(*)::int AS total
           FROM catalogo.campania
           GROUP BY estado
           ORDER BY estado`,
    params: [],
  };
}

export function sqlIntervencionesPorEstado(unidadId) {
  const params = [];
  const where = unidadId ? (params.push(unidadId), "WHERE unidad_organizacional_id = $1") : "";
  return {
    text: `SELECT estado, COUNT(*)::int AS total
           FROM intervencion.plan
           ${where}
           GROUP BY estado
           ORDER BY estado`,
    params,
  };
}

export function sqlReglasPorNivel() {
  return {
    text: `SELECT nivel, COUNT(*)::int AS total
           FROM riesgo.regla
           WHERE activa
           GROUP BY nivel
           ORDER BY nivel`,
    params: [],
  };
}

export function sqlFuentes() {
  return {
    text: `SELECT CASE WHEN autorizada THEN 'Autorizadas' ELSE 'Prohibidas' END AS categoria,
                  COUNT(*)::int AS total
           FROM catalogo.fuente_autorizada
           GROUP BY autorizada
           ORDER BY autorizada DESC`,
    params: [],
  };
}

export function sqlParticipacion(unidadId) {
  const params = [];
  const extra = unidadId ? (params.push(unidadId), "AND r.unidad_organizacional_id = $1") : "";
  return {
    text: `SELECT c.secuencia, c.campania_id, c.nombre, COUNT(r.respuesta_id)::int AS n
           FROM catalogo.campania c
           LEFT JOIN autoreporte.respuesta r
             ON r.campania_id = c.campania_id
             ${extra}
           GROUP BY c.secuencia, c.campania_id, c.nombre
           ORDER BY c.secuencia`,
    params,
  };
}

export function sqlTendencia(unidadId, dimensionId) {
  const params = [];
  const partes = [];
  if (unidadId) {
    params.push(unidadId);
    partes.push(`unidad_organizacional_id = $${params.length}`);
  }
  if (dimensionId) {
    params.push(dimensionId);
    partes.push(`dimension_id = $${params.length}`);
  } else {
    partes.push("dimension_id IS NULL");
  }
  return {
    text: `SELECT secuencia, campania_id, campania_nombre AS nombre,
                  valor_protegido::float8 AS valor_protegido
           FROM agregado.v_tendencia
           WHERE ${partes.join(" AND ")}
           ORDER BY secuencia`,
    params,
  };
}

export function sqlUmbralK() {
  return {
    text: `SELECT valor::int AS k FROM agregado.parametro_privacidad WHERE clave = 'k_umbral_minimo'`,
    params: [],
  };
}

export function sqlAuditoriaPorAccion(desde, hasta) {
  return {
    text: `SELECT accion, COUNT(*)::int AS total
           FROM auditoria.bitacora
           WHERE ($1::date IS NULL OR fecha_hora >= $1::date)
             AND ($2::date IS NULL OR fecha_hora < ($2::date + INTERVAL '1 day'))
           GROUP BY accion
           ORDER BY total DESC, accion`,
    params: [desde, hasta],
  };
}

export function sqlAuditoriaPorPeriodo(desde, hasta) {
  return {
    text: `SELECT to_char(fecha_hora::date, 'YYYY-MM-DD') AS dia, COUNT(*)::int AS total
           FROM auditoria.bitacora
           WHERE ($1::date IS NULL OR fecha_hora >= $1::date)
             AND ($2::date IS NULL OR fecha_hora < ($2::date + INTERVAL '1 day'))
           GROUP BY fecha_hora::date
           ORDER BY fecha_hora::date`,
    params: [desde, hasta],
  };
}

export function sqlPublicacion(unidadId) {
  const params = [];
  const where = unidadId ? (params.push(unidadId), "WHERE unidad_organizacional_id = $1") : "";
  return {
    text: `SELECT estado_publicacion AS estado, COUNT(*)::int AS total
           FROM agregado.resultado_protegido
           ${where}
           GROUP BY estado_publicacion
           ORDER BY estado_publicacion`,
    params,
  };
}

export function sqlEventosAuditoria() {
  return { text: "SELECT COUNT(*)::int AS total FROM auditoria.bitacora", params: [] };
}
