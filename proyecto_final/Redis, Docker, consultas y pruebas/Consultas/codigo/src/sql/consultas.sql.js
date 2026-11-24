import { comoPatronLike } from "../../../comun/src/paginacion.js";

function donde(partes) {
  return partes.length ? `WHERE ${partes.join(" AND ")}` : "";
}

export function sqlCampanias(filtros) {
  const partes = [];
  const params = [];
  if (filtros.estado) {
    params.push(filtros.estado);
    partes.push(`c.estado = $${params.length}`);
  }
  if (filtros.search) {
    params.push(comoPatronLike(filtros.search));
    partes.push(`c.nombre ILIKE $${params.length} ESCAPE '\\'`);
  }
  const filtro = donde(partes);
  const countParams = [...params];
  params.push(filtros.limit, filtros.offset);
  return {
    text: `SELECT c.campania_id, c.nombre, c.estado,
                  c.fecha_inicio::text AS fecha_inicio,
                  c.fecha_fin::text AS fecha_fin,
                  c.secuencia, c.instrumento_id, c.version_instrumento,
                  (c.estado = 'ABIERTA') AS activa
           FROM catalogo.campania c
           ${filtro}
           ORDER BY ${filtros.columna} ${filtros.order}, c.campania_id
           LIMIT $${params.length - 1} OFFSET $${params.length}`,
    params,
    countText: `SELECT COUNT(*)::int AS total FROM catalogo.campania c ${filtro}`,
    countParams,
  };
}

export function sqlCampaniaPorId(id) {
  return {
    text: `SELECT c.campania_id, c.nombre, c.estado,
                  c.fecha_inicio::text AS fecha_inicio,
                  c.fecha_fin::text AS fecha_fin,
                  c.secuencia, c.instrumento_id, c.version_instrumento,
                  (c.estado = 'ABIERTA') AS activa
           FROM catalogo.campania c
           WHERE c.campania_id = $1`,
    params: [id],
  };
}

export function sqlUnidades(filtros) {
  const partes = [];
  const params = [];
  if (filtros.tipo) {
    params.push(filtros.tipo);
    partes.push(`u.tipo = $${params.length}`);
  }
  if (filtros.activa != null) {
    params.push(filtros.activa);
    partes.push(`u.activa = $${params.length}`);
  }
  if (filtros.search) {
    params.push(comoPatronLike(filtros.search));
    partes.push(`u.nombre ILIKE $${params.length} ESCAPE '\\'`);
  }
  const filtro = donde(partes);
  const countParams = [...params];
  params.push(filtros.limit, filtros.offset);
  return {
    text: `SELECT u.unidad_organizacional_id, u.nombre, u.tipo,
                  u.unidad_padre_id, u.nivel_jerarquico, u.plantilla_declarada, u.activa
           FROM organizacion.unidad_organizacional u
           ${filtro}
           ORDER BY ${filtros.columna} ${filtros.order}, u.unidad_organizacional_id
           LIMIT $${params.length - 1} OFFSET $${params.length}`,
    params,
    countText: `SELECT COUNT(*)::int AS total FROM organizacion.unidad_organizacional u ${filtro}`,
    countParams,
  };
}

export function sqlUnidadPorId(id) {
  return {
    text: `SELECT unidad_organizacional_id, nombre, tipo, unidad_padre_id,
                  nivel_jerarquico, plantilla_declarada, activa
           FROM organizacion.unidad_organizacional
           WHERE unidad_organizacional_id = $1`,
    params: [id],
  };
}

export function sqlInstrumentos(filtros) {
  const partes = ["i.activo = TRUE"];
  const params = [];
  if (filtros.search) {
    params.push(comoPatronLike(filtros.search));
    partes.push(`i.nombre ILIKE $${params.length} ESCAPE '\\'`);
  }
  const filtro = donde(partes);
  const countParams = [...params];
  params.push(filtros.limit, filtros.offset);
  return {
    text: `SELECT i.instrumento_id, i.nombre, i.tipo, i.activo
           FROM catalogo.instrumento i
           ${filtro}
           ORDER BY i.nombre
           LIMIT $${params.length - 1} OFFSET $${params.length}`,
    params,
    countText: `SELECT COUNT(*)::int AS total FROM catalogo.instrumento i ${filtro}`,
    countParams,
  };
}

export function sqlFuentes(filtros) {
  const partes = [];
  const params = [];
  if (filtros.autorizada != null) {
    params.push(filtros.autorizada);
    partes.push(`f.autorizada = $${params.length}`);
  }
  if (filtros.search) {
    params.push(comoPatronLike(filtros.search));
    partes.push(`f.nombre ILIKE $${params.length} ESCAPE '\\'`);
  }
  const filtro = donde(partes);
  const countParams = [...params];
  params.push(filtros.limit, filtros.offset);
  return {
    text: `SELECT f.fuente_id, f.nombre, f.autorizada, f.motivo
           FROM catalogo.fuente_autorizada f
           ${filtro}
           ORDER BY f.autorizada DESC, f.nombre
           LIMIT $${params.length - 1} OFFSET $${params.length}`,
    params,
    countText: `SELECT COUNT(*)::int AS total FROM catalogo.fuente_autorizada f ${filtro}`,
    countParams,
  };
}

export function sqlIntervenciones(filtros) {
  const partes = [];
  const params = [];
  if (filtros.unidad_organizacional_id) {
    params.push(filtros.unidad_organizacional_id);
    partes.push(`p.unidad_organizacional_id = $${params.length}`);
  }
  if (filtros.estado) {
    params.push(filtros.estado);
    partes.push(`p.estado = $${params.length}`);
  }
  if (filtros.search) {
    params.push(comoPatronLike(filtros.search));
    partes.push(`(p.justificacion ILIKE $${params.length} ESCAPE '\\' OR t.nombre ILIKE $${params.length} ESCAPE '\\')`);
  }
  const filtro = donde(partes);
  const countParams = [...params];
  params.push(filtros.limit, filtros.offset);
  return {
    text: `SELECT p.intervencion_id::text AS intervencion_id,
                  p.unidad_organizacional_id, u.nombre AS unidad,
                  p.tipo_intervencion, t.nombre AS tipo_nombre, p.estado,
                  p.fecha_inicio::text AS fecha_inicio,
                  p.fecha_fin::text AS fecha_fin,
                  p.justificacion, p.resultado_esperado,
                  p.campania_linea_base
           FROM intervencion.plan p
           JOIN intervencion.tipo_intervencion t ON t.tipo_intervencion = p.tipo_intervencion
           JOIN organizacion.unidad_organizacional u ON u.unidad_organizacional_id = p.unidad_organizacional_id
           ${filtro}
           ORDER BY ${filtros.columna} ${filtros.order}, p.intervencion_id
           LIMIT $${params.length - 1} OFFSET $${params.length}`,
    params,
    countText: `SELECT COUNT(*)::int AS total
                FROM intervencion.plan p
                JOIN intervencion.tipo_intervencion t ON t.tipo_intervencion = p.tipo_intervencion
                ${filtro}`,
    countParams,
  };
}

export function sqlIntervencionPorId(id) {
  return {
    text: `SELECT p.intervencion_id::text AS intervencion_id,
                  p.unidad_organizacional_id, u.nombre AS unidad,
                  p.tipo_intervencion, t.nombre AS tipo_nombre, p.estado,
                  p.fecha_inicio::text AS fecha_inicio,
                  p.fecha_fin::text AS fecha_fin,
                  p.justificacion, p.resultado_esperado, p.campania_linea_base
           FROM intervencion.plan p
           JOIN intervencion.tipo_intervencion t ON t.tipo_intervencion = p.tipo_intervencion
           JOIN organizacion.unidad_organizacional u ON u.unidad_organizacional_id = p.unidad_organizacional_id
           WHERE p.intervencion_id = $1`,
    params: [id],
  };
}

export function sqlAuditoria(filtros) {
  const partes = [];
  const params = [];
  if (filtros.accion) {
    params.push(filtros.accion);
    partes.push(`b.accion = $${params.length}`);
  }
  if (filtros.resultado) {
    params.push(filtros.resultado);
    partes.push(`b.resultado = $${params.length}`);
  }
  if (filtros.desde) {
    params.push(filtros.desde);
    partes.push(`b.fecha_hora >= $${params.length}::date`);
  }
  if (filtros.hasta) {
    params.push(filtros.hasta);
    partes.push(`b.fecha_hora < ($${params.length}::date + INTERVAL '1 day')`);
  }
  if (filtros.search) {
    params.push(comoPatronLike(filtros.search));
    partes.push(`(b.actor_usuario_id ILIKE $${params.length} ESCAPE '\\'
                 OR b.correlacion_id ILIKE $${params.length} ESCAPE '\\'
                 OR b.accion ILIKE $${params.length} ESCAPE '\\')`);
  }
  const filtro = donde(partes);
  const countParams = [...params];
  params.push(filtros.limit, filtros.offset);
  return {
    text: `SELECT b.fecha_hora, b.actor_usuario_id, b.actor_nombre, b.actor_perfil,
                  b.accion, b.accion_descripcion, b.tipo_recurso, b.recurso_id,
                  b.resultado, b.correlacion_id
           FROM auditoria.v_tablero_auditoria b
           ${filtro}
           ORDER BY b.fecha_hora DESC
           LIMIT $${params.length - 1} OFFSET $${params.length}`,
    params,
    countText: `SELECT COUNT(*)::int AS total FROM auditoria.v_tablero_auditoria b ${filtro}`,
    countParams,
  };
}

export function sqlResultados(filtros) {
  const partes = [];
  const params = [];
  if (filtros.unidad_organizacional_id) {
    params.push(filtros.unidad_organizacional_id);
    partes.push(`t.unidad_organizacional_id = $${params.length}`);
  }
  if (filtros.campania_id) {
    params.push(filtros.campania_id);
    partes.push(`t.campania_id = $${params.length}`);
  }
  if (filtros.estado) {
    params.push(filtros.estado);
    partes.push(`t.estado_publicacion = $${params.length}`);
  }
  const filtro = donde(partes);
  const countParams = [...params];
  params.push(filtros.limit, filtros.offset);
  return {
    text: `SELECT t.unidad_organizacional_id, t.unidad, t.campania_id, t.secuencia,
                  t.dimension, t.estado_publicacion, t.participacion_protegida,
                  t.precision_advertencia, t.valor_protegido::float8 AS valor_protegido,
                  t.epsilon_aplicado::float8 AS epsilon_aplicado, t.mecanismo
           FROM agregado.v_tablero_unidad t
           ${filtro}
           ORDER BY t.secuencia DESC, t.unidad, t.dimension
           LIMIT $${params.length - 1} OFFSET $${params.length}`,
    params,
    countText: `SELECT COUNT(*)::int AS total FROM agregado.v_tablero_unidad t ${filtro}`,
    countParams,
  };
}

export function sqlPresupuesto(filtros) {
  const partes = [];
  const params = [];
  if (filtros.unidad_organizacional_id) {
    params.push(filtros.unidad_organizacional_id);
    partes.push(`p.unidad_organizacional_id = $${params.length}`);
  }
  if (filtros.campania_id) {
    params.push(filtros.campania_id);
    partes.push(`p.campania_id = $${params.length}`);
  }
  if (filtros.agotado != null) {
    params.push(filtros.agotado);
    partes.push(`p.agotado = $${params.length}`);
  }
  const filtro = donde(partes);
  const countParams = [...params];
  params.push(filtros.limit, filtros.offset);
  return {
    text: `SELECT p.campania_id, p.unidad_organizacional_id, p.unidad,
                  p.epsilon_total::float8 AS epsilon_total,
                  p.epsilon_consumido::float8 AS epsilon_consumido,
                  p.epsilon_restante::float8 AS epsilon_restante,
                  p.agotado, p.consultas_realizadas::int AS consultas_realizadas
           FROM agregado.v_estado_presupuesto p
           ${filtro}
           ORDER BY p.unidad, p.campania_id
           LIMIT $${params.length - 1} OFFSET $${params.length}`,
    params,
    countText: `SELECT COUNT(*)::int AS total FROM agregado.v_estado_presupuesto p ${filtro}`,
    countParams,
  };
}

export function sqlParticipacion(usuarioId) {
  return {
    text: `SELECT estado_consentimiento,
                  fecha_consentimiento::text AS fecha_consentimiento,
                  campanias_respondidas::int AS campanias_respondidas,
                  ultima_participacion::text AS ultima_participacion
           FROM portal.v_participacion_propia
           WHERE usuario_id = $1`,
    params: [usuarioId],
  };
}
