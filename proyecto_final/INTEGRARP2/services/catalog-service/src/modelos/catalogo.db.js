import { pgQuery } from "../config/postgres.js";

// ============================================================================
// 1. UNIDADES ORGANIZACIONALES
// ============================================================================

export async function dbListarUnidades({
  activa,
  nombre,
  unidad_padre_id,
  page = 1,
  limit = 10,
} = {}) {
  const condiciones = [];
  const valores = [];
  let idx = 1;

  if (activa !== undefined && activa !== null && activa !== "") {
    condiciones.push(`activa = $${idx++}`);
    valores.push(String(activa) === "true");
  }
  if (nombre) {
    condiciones.push(`nombre ILIKE $${idx++}`);
    valores.push(`%${nombre}%`);
  }
  if (unidad_padre_id !== undefined && unidad_padre_id !== null && unidad_padre_id !== "") {
    condiciones.push(`unidad_padre_id = $${idx++}`);
    valores.push(unidad_padre_id);
  }

  const whereClause = condiciones.length ? `WHERE ${condiciones.join(" AND ")}` : "";

  const totalRes = await pgQuery(
    `SELECT count(*)::int AS total FROM organizacion.unidad_organizacional ${whereClause}`,
    valores
  );
  const total = totalRes.rows[0]?.total || 0;

  const numPage = Math.max(1, Number(page) || 1);
  const numLimit = Math.max(1, Math.min(100, Number(limit) || 10));
  const offset = (numPage - 1) * numLimit;

  valores.push(numLimit, offset);
  const dataRes = await pgQuery(
    `SELECT unidad_organizacional_id, nombre, descripcion, unidad_padre_id,
            nivel_jerarquico, activa, fecha_creacion, fecha_actualizacion
     FROM organizacion.unidad_organizacional
     ${whereClause}
     ORDER BY nombre ASC
     LIMIT $${idx++} OFFSET $${idx++}`,
    valores
  );

  return {
    rows: dataRes.rows,
    total,
    page: numPage,
    limit: numLimit,
    totalPages: Math.ceil(total / numLimit) || 1,
  };
}

export async function dbObtenerUnidadPorId(id) {
  const r = await pgQuery(
    `SELECT unidad_organizacional_id, nombre, descripcion, unidad_padre_id,
            nivel_jerarquico, activa, fecha_creacion, fecha_actualizacion
     FROM organizacion.unidad_organizacional
     WHERE unidad_organizacional_id = $1`,
    [id]
  );
  return r.rows[0] || null;
}

export async function dbCrearUnidad({
  unidad_organizacional_id,
  nombre,
  descripcion,
  unidad_padre_id,
  nivel_jerarquico = 0,
  activa = true,
}) {
  const r = await pgQuery(
    `INSERT INTO organizacion.unidad_organizacional (
        unidad_organizacional_id, nombre, descripcion, unidad_padre_id, nivel_jerarquico, activa
     ) VALUES ($1, $2, $3, $4, $5, $6)
     RETURNING unidad_organizacional_id, nombre, descripcion, unidad_padre_id,
               nivel_jerarquico, activa, fecha_creacion, fecha_actualizacion`,
    [unidad_organizacional_id, nombre, descripcion || null, unidad_padre_id || null, nivel_jerarquico, activa]
  );
  return r.rows[0];
}

export async function dbActualizarUnidad(id, { nombre, descripcion, unidad_padre_id, nivel_jerarquico, activa }) {
  const campos = [];
  const valores = [id];
  let idx = 2;

  if (nombre !== undefined) {
    campos.push(`nombre = $${idx++}`);
    valores.push(nombre);
  }
  if (descripcion !== undefined) {
    campos.push(`descripcion = $${idx++}`);
    valores.push(descripcion);
  }
  if (unidad_padre_id !== undefined) {
    campos.push(`unidad_padre_id = $${idx++}`);
    valores.push(unidad_padre_id || null);
  }
  if (nivel_jerarquico !== undefined) {
    campos.push(`nivel_jerarquico = $${idx++}`);
    valores.push(Number(nivel_jerarquico));
  }
  if (activa !== undefined) {
    campos.push(`activa = $${idx++}`);
    valores.push(Boolean(activa));
  }

  if (campos.length === 0) {
    return dbObtenerUnidadPorId(id);
  }

  const r = await pgQuery(
    `UPDATE organizacion.unidad_organizacional
     SET ${campos.join(", ")}
     WHERE unidad_organizacional_id = $1
     RETURNING unidad_organizacional_id, nombre, descripcion, unidad_padre_id,
               nivel_jerarquico, activa, fecha_creacion, fecha_actualizacion`,
    valores
  );
  return r.rows[0] || null;
}

export async function dbEliminarUnidadLogica(id) {
  const r = await pgQuery(
    `UPDATE organizacion.unidad_organizacional
     SET activa = FALSE
     WHERE unidad_organizacional_id = $1
     RETURNING unidad_organizacional_id, nombre, activa, fecha_actualizacion`,
    [id]
  );
  return r.rows[0] || null;
}

// ============================================================================
// 2. INSTRUMENTOS Y VERSIONES
// ============================================================================

export async function dbListarInstrumentos({
  activo,
  tipo,
  nombre,
  page = 1,
  limit = 10,
} = {}) {
  const condiciones = [];
  const valores = [];
  let idx = 1;

  if (activo !== undefined && activo !== null && activo !== "") {
    condiciones.push(`activo = $${idx++}`);
    valores.push(String(activo) === "true");
  }
  if (tipo) {
    condiciones.push(`tipo = $${idx++}`);
    valores.push(tipo);
  }
  if (nombre) {
    condiciones.push(`nombre ILIKE $${idx++}`);
    valores.push(`%${nombre}%`);
  }

  const whereClause = condiciones.length ? `WHERE ${condiciones.join(" AND ")}` : "";

  const totalRes = await pgQuery(
    `SELECT count(*)::int AS total FROM catalogo.instrumento ${whereClause}`,
    valores
  );
  const total = totalRes.rows[0]?.total || 0;

  const numPage = Math.max(1, Number(page) || 1);
  const numLimit = Math.max(1, Math.min(100, Number(limit) || 10));
  const offset = (numPage - 1) * numLimit;

  valores.push(numLimit, offset);
  const dataRes = await pgQuery(
    `SELECT instrumento_id, nombre, descripcion, tipo, activo,
            fecha_creacion, fecha_actualizacion
     FROM catalogo.instrumento
     ${whereClause}
     ORDER BY nombre ASC
     LIMIT $${idx++} OFFSET $${idx++}`,
    valores
  );

  return {
    rows: dataRes.rows,
    total,
    page: numPage,
    limit: numLimit,
    totalPages: Math.ceil(total / numLimit) || 1,
  };
}

export async function dbObtenerInstrumentoPorId(id) {
  const r = await pgQuery(
    `SELECT instrumento_id, nombre, descripcion, tipo, activo,
            fecha_creacion, fecha_actualizacion
     FROM catalogo.instrumento
     WHERE instrumento_id = $1`,
    [id]
  );
  if (!r.rows[0]) return null;

  const versiones = await pgQuery(
    `SELECT instrumento_id, version, fecha_vigencia_desde, fecha_vigencia_hasta,
            archivo_plantilla, activo, fecha_creacion, fecha_actualizacion
     FROM catalogo.version_instrumento
     WHERE instrumento_id = $1
     ORDER BY version DESC`,
    [id]
  );

  return {
    ...r.rows[0],
    versiones: versiones.rows,
  };
}

export async function dbCrearInstrumento({
  instrumento_id,
  nombre,
  descripcion,
  tipo,
  activo = true,
}) {
  const r = await pgQuery(
    `INSERT INTO catalogo.instrumento (instrumento_id, nombre, descripcion, tipo, activo)
     VALUES ($1, $2, $3, $4, $5)
     RETURNING instrumento_id, nombre, descripcion, tipo, activo,
               fecha_creacion, fecha_actualizacion`,
    [instrumento_id, nombre, descripcion || null, tipo, activo]
  );
  return r.rows[0];
}

export async function dbActualizarInstrumento(id, { nombre, descripcion, tipo, activo }) {
  const campos = [];
  const valores = [id];
  let idx = 2;

  if (nombre !== undefined) {
    campos.push(`nombre = $${idx++}`);
    valores.push(nombre);
  }
  if (descripcion !== undefined) {
    campos.push(`descripcion = $${idx++}`);
    valores.push(descripcion);
  }
  if (tipo !== undefined) {
    campos.push(`tipo = $${idx++}`);
    valores.push(tipo);
  }
  if (activo !== undefined) {
    campos.push(`activo = $${idx++}`);
    valores.push(Boolean(activo));
  }

  if (campos.length === 0) {
    return dbObtenerInstrumentoPorId(id);
  }

  const r = await pgQuery(
    `UPDATE catalogo.instrumento
     SET ${campos.join(", ")}
     WHERE instrumento_id = $1
     RETURNING instrumento_id, nombre, descripcion, tipo, activo,
               fecha_creacion, fecha_actualizacion`,
    valores
  );
  return r.rows[0] || null;
}

export async function dbEliminarInstrumentoLogico(id) {
  const r = await pgQuery(
    `UPDATE catalogo.instrumento
     SET activo = FALSE
     WHERE instrumento_id = $1
     RETURNING instrumento_id, nombre, activo, fecha_actualizacion`,
    [id]
  );
  return r.rows[0] || null;
}

// Versiones de Instrumento

export async function dbListarVersiones(instrumento_id, { activo } = {}) {
  const condiciones = ["instrumento_id = $1"];
  const valores = [instrumento_id];
  let idx = 2;

  if (activo !== undefined && activo !== null && activo !== "") {
    condiciones.push(`activo = $${idx++}`);
    valores.push(String(activo) === "true");
  }

  const r = await pgQuery(
    `SELECT instrumento_id, version, fecha_vigencia_desde, fecha_vigencia_hasta,
            archivo_plantilla, activo, fecha_creacion, fecha_actualizacion
     FROM catalogo.version_instrumento
     WHERE ${condiciones.join(" AND ")}
     ORDER BY version DESC`,
    valores
  );
  return r.rows;
}

export async function dbObtenerVersion(instrumento_id, version) {
  const r = await pgQuery(
    `SELECT instrumento_id, version, fecha_vigencia_desde, fecha_vigencia_hasta,
            archivo_plantilla, activo, fecha_creacion, fecha_actualizacion
     FROM catalogo.version_instrumento
     WHERE instrumento_id = $1 AND version = $2`,
    [instrumento_id, Number(version)]
  );
  return r.rows[0] || null;
}

export async function dbCrearVersion({
  instrumento_id,
  version,
  fecha_vigencia_desde,
  fecha_vigencia_hasta,
  archivo_plantilla,
  activo = true,
}) {
  const r = await pgQuery(
    `INSERT INTO catalogo.version_instrumento (
        instrumento_id, version, fecha_vigencia_desde, fecha_vigencia_hasta,
        archivo_plantilla, activo
     ) VALUES ($1, $2, $3, $4, $5, $6)
     RETURNING instrumento_id, version, fecha_vigencia_desde, fecha_vigencia_hasta,
               archivo_plantilla, activo, fecha_creacion, fecha_actualizacion`,
    [
      instrumento_id,
      Number(version),
      fecha_vigencia_desde,
      fecha_vigencia_hasta || null,
      archivo_plantilla || null,
      activo,
    ]
  );
  return r.rows[0];
}

export async function dbActualizarVersion(
  instrumento_id,
  version,
  { fecha_vigencia_desde, fecha_vigencia_hasta, archivo_plantilla, activo }
) {
  const campos = [];
  const valores = [instrumento_id, Number(version)];
  let idx = 3;

  if (fecha_vigencia_desde !== undefined) {
    campos.push(`fecha_vigencia_desde = $${idx++}`);
    valores.push(fecha_vigencia_desde);
  }
  if (fecha_vigencia_hasta !== undefined) {
    campos.push(`fecha_vigencia_hasta = $${idx++}`);
    valores.push(fecha_vigencia_hasta || null);
  }
  if (archivo_plantilla !== undefined) {
    campos.push(`archivo_plantilla = $${idx++}`);
    valores.push(archivo_plantilla || null);
  }
  if (activo !== undefined) {
    campos.push(`activo = $${idx++}`);
    valores.push(Boolean(activo));
  }

  if (campos.length === 0) {
    return dbObtenerVersion(instrumento_id, version);
  }

  const r = await pgQuery(
    `UPDATE catalogo.version_instrumento
     SET ${campos.join(", ")}
     WHERE instrumento_id = $1 AND version = $2
     RETURNING instrumento_id, version, fecha_vigencia_desde, fecha_vigencia_hasta,
               archivo_plantilla, activo, fecha_creacion, fecha_actualizacion`,
    valores
  );
  return r.rows[0] || null;
}

export async function dbEliminarVersionLogica(instrumento_id, version) {
  const r = await pgQuery(
    `UPDATE catalogo.version_instrumento
     SET activo = FALSE
     WHERE instrumento_id = $1 AND version = $2
     RETURNING instrumento_id, version, activo, fecha_actualizacion`,
    [instrumento_id, Number(version)]
  );
  return r.rows[0] || null;
}

// ============================================================================
// 3. REACTIVOS Y VINCULACIÓN A VERSIONES
// ============================================================================

export async function dbListarReactivos({
  activo,
  dimension,
  q,
  page = 1,
  limit = 10,
} = {}) {
  const condiciones = [];
  const valores = [];
  let idx = 1;

  if (activo !== undefined && activo !== null && activo !== "") {
    condiciones.push(`activo = $${idx++}`);
    valores.push(String(activo) === "true");
  }
  if (dimension) {
    condiciones.push(`dimension ILIKE $${idx++}`);
    valores.push(`%${dimension}%`);
  }
  if (q) {
    condiciones.push(`texto ILIKE $${idx++}`);
    valores.push(`%${q}%`);
  }

  const whereClause = condiciones.length ? `WHERE ${condiciones.join(" AND ")}` : "";

  const totalRes = await pgQuery(
    `SELECT count(*)::int AS total FROM catalogo.reactivo ${whereClause}`,
    valores
  );
  const total = totalRes.rows[0]?.total || 0;

  const numPage = Math.max(1, Number(page) || 1);
  const numLimit = Math.max(1, Math.min(100, Number(limit) || 10));
  const offset = (numPage - 1) * numLimit;

  valores.push(numLimit, offset);
  const dataRes = await pgQuery(
    `SELECT reactivo_id, texto, dimension, escala_min, escala_max,
            invertido, activo, fecha_creacion, fecha_actualizacion
     FROM catalogo.reactivo
     ${whereClause}
     ORDER BY reactivo_id ASC
     LIMIT $${idx++} OFFSET $${idx++}`,
    valores
  );

  return {
    rows: dataRes.rows,
    total,
    page: numPage,
    limit: numLimit,
    totalPages: Math.ceil(total / numLimit) || 1,
  };
}

export async function dbObtenerReactivoPorId(id) {
  const r = await pgQuery(
    `SELECT reactivo_id, texto, dimension, escala_min, escala_max,
            invertido, activo, fecha_creacion, fecha_actualizacion
     FROM catalogo.reactivo
     WHERE reactivo_id = $1`,
    [id]
  );
  return r.rows[0] || null;
}

export async function dbCrearReactivo({
  reactivo_id,
  texto,
  dimension,
  escala_min = 1,
  escala_max = 5,
  invertido = false,
  activo = true,
}) {
  const r = await pgQuery(
    `INSERT INTO catalogo.reactivo (
        reactivo_id, texto, dimension, escala_min, escala_max, invertido, activo
     ) VALUES ($1, $2, $3, $4, $5, $6, $7)
     RETURNING reactivo_id, texto, dimension, escala_min, escala_max,
               invertido, activo, fecha_creacion, fecha_actualizacion`,
    [reactivo_id, texto, dimension || null, Number(escala_min), Number(escala_max), Boolean(invertido), Boolean(activo)]
  );
  return r.rows[0];
}

export async function dbActualizarReactivo(
  id,
  { texto, dimension, escala_min, escala_max, invertido, activo }
) {
  const campos = [];
  const valores = [id];
  let idx = 2;

  if (texto !== undefined) {
    campos.push(`texto = $${idx++}`);
    valores.push(texto);
  }
  if (dimension !== undefined) {
    campos.push(`dimension = $${idx++}`);
    valores.push(dimension);
  }
  if (escala_min !== undefined) {
    campos.push(`escala_min = $${idx++}`);
    valores.push(Number(escala_min));
  }
  if (escala_max !== undefined) {
    campos.push(`escala_max = $${idx++}`);
    valores.push(Number(escala_max));
  }
  if (invertido !== undefined) {
    campos.push(`invertido = $${idx++}`);
    valores.push(Boolean(invertido));
  }
  if (activo !== undefined) {
    campos.push(`activo = $${idx++}`);
    valores.push(Boolean(activo));
  }

  if (campos.length === 0) {
    return dbObtenerReactivoPorId(id);
  }

  const r = await pgQuery(
    `UPDATE catalogo.reactivo
     SET ${campos.join(", ")}
     WHERE reactivo_id = $1
     RETURNING reactivo_id, texto, dimension, escala_min, escala_max,
               invertido, activo, fecha_creacion, fecha_actualizacion`,
    valores
  );
  return r.rows[0] || null;
}

export async function dbEliminarReactivoLogico(id) {
  const r = await pgQuery(
    `UPDATE catalogo.reactivo
     SET activo = FALSE
     WHERE reactivo_id = $1
     RETURNING reactivo_id, texto, activo, fecha_actualizacion`,
    [id]
  );
  return r.rows[0] || null;
}

// Reactivo <-> Instrumento Versión
export async function dbListarReactivosDeVersion(instrumento_id, version) {
  const r = await pgQuery(
    `SELECT r.reactivo_id, r.texto, r.dimension, r.escala_min, r.escala_max,
            r.invertido, r.activo, riv.orden, riv.obligatorio
     FROM catalogo.reactivo_instrumento_version riv
     JOIN catalogo.reactivo r ON r.reactivo_id = riv.reactivo_id
     WHERE riv.instrumento_id = $1 AND riv.version = $2 AND r.activo = TRUE
     ORDER BY riv.orden ASC`,
    [instrumento_id, Number(version)]
  );
  return r.rows;
}

export async function dbAsociarReactivoAVersion(
  instrumento_id,
  version,
  { reactivo_id, orden, obligatorio = true }
) {
  const r = await pgQuery(
    `INSERT INTO catalogo.reactivo_instrumento_version (
        instrumento_id, version, reactivo_id, orden, obligatorio
     ) VALUES ($1, $2, $3, $4, $5)
     ON CONFLICT (instrumento_id, version, reactivo_id)
     DO UPDATE SET orden = EXCLUDED.orden, obligatorio = EXCLUDED.obligatorio
     RETURNING instrumento_id, version, reactivo_id, orden, obligatorio`,
    [instrumento_id, Number(version), reactivo_id, Number(orden), Boolean(obligatorio)]
  );
  return r.rows[0];
}

export async function dbDesasociarReactivoDeVersion(instrumento_id, version, reactivo_id) {
  const r = await pgQuery(
    `DELETE FROM catalogo.reactivo_instrumento_version
     WHERE instrumento_id = $1 AND version = $2 AND reactivo_id = $3
     RETURNING instrumento_id, version, reactivo_id`,
    [instrumento_id, Number(version), reactivo_id]
  );
  return r.rows[0] || null;
}

// ============================================================================
// 4. CAMPAÑAS Y ASIGNACIÓN A UNIDADES
// ============================================================================

export async function dbListarCampanias({
  activa,
  instrumento_id,
  unidad_organizacional_id,
  page = 1,
  limit = 10,
} = {}) {
  const condiciones = [];
  const valores = [];
  let idx = 1;

  let joinClause = "";
  if (unidad_organizacional_id) {
    joinClause = `JOIN catalogo.campania_unidad cu ON cu.campania_id = c.campania_id AND cu.unidad_organizacional_id = $${idx++}`;
    valores.push(unidad_organizacional_id);
  }

  if (activa !== undefined && activa !== null && activa !== "") {
    condiciones.push(`c.activa = $${idx++}`);
    valores.push(String(activa) === "true");
  }
  if (instrumento_id) {
    condiciones.push(`c.instrumento_id = $${idx++}`);
    valores.push(instrumento_id);
  }

  const whereClause = condiciones.length ? `WHERE ${condiciones.join(" AND ")}` : "";

  const totalRes = await pgQuery(
    `SELECT count(DISTINCT c.campania_id)::int AS total
     FROM catalogo.campania c
     ${joinClause}
     ${whereClause}`,
    valores
  );
  const total = totalRes.rows[0]?.total || 0;

  const numPage = Math.max(1, Number(page) || 1);
  const numLimit = Math.max(1, Math.min(100, Number(limit) || 10));
  const offset = (numPage - 1) * numLimit;

  valores.push(numLimit, offset);
  const dataRes = await pgQuery(
    `SELECT c.campania_id, c.nombre, c.descripcion, c.fecha_inicio, c.fecha_fin,
            c.instrumento_id, c.version_instrumento, c.activa,
            c.fecha_creacion, c.fecha_actualizacion
     FROM catalogo.campania c
     ${joinClause}
     ${whereClause}
     ORDER BY c.fecha_inicio DESC
     LIMIT $${idx++} OFFSET $${idx++}`,
    valores
  );

  return {
    rows: dataRes.rows,
    total,
    page: numPage,
    limit: numLimit,
    totalPages: Math.ceil(total / numLimit) || 1,
  };
}

export async function dbObtenerCampaniaPorId(id) {
  const r = await pgQuery(
    `SELECT campania_id, nombre, descripcion, fecha_inicio, fecha_fin,
            instrumento_id, version_instrumento, activa,
            fecha_creacion, fecha_actualizacion
     FROM catalogo.campania
     WHERE campania_id = $1`,
    [id]
  );
  if (!r.rows[0]) return null;

  const unidades = await pgQuery(
    `SELECT cu.unidad_organizacional_id, u.nombre, cu.fecha_apertura, cu.fecha_cierre
     FROM catalogo.campania_unidad cu
     JOIN organizacion.unidad_organizacional u ON u.unidad_organizacional_id = cu.unidad_organizacional_id
     WHERE cu.campania_id = $1
     ORDER BY u.nombre ASC`,
    [id]
  );

  return {
    ...r.rows[0],
    unidades: unidades.rows,
  };
}

export async function dbCrearCampania({
  campania_id,
  nombre,
  descripcion,
  fecha_inicio,
  fecha_fin,
  instrumento_id,
  version_instrumento,
  activa = true,
  unidades_ids = [],
}) {
  const r = await pgQuery(
    `INSERT INTO catalogo.campania (
        campania_id, nombre, descripcion, fecha_inicio, fecha_fin,
        instrumento_id, version_instrumento, activa
     ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
     RETURNING campania_id, nombre, descripcion, fecha_inicio, fecha_fin,
               instrumento_id, version_instrumento, activa,
               fecha_creacion, fecha_actualizacion`,
    [
      campania_id,
      nombre,
      descripcion || null,
      fecha_inicio,
      fecha_fin,
      instrumento_id,
      Number(version_instrumento),
      Boolean(activa),
    ]
  );

  if (Array.isArray(unidades_ids) && unidades_ids.length > 0) {
    for (const uId of unidades_ids) {
      await pgQuery(
        `INSERT INTO catalogo.campania_unidad (campania_id, unidad_organizacional_id)
         VALUES ($1, $2)
         ON CONFLICT (campania_id, unidad_organizacional_id) DO NOTHING`,
        [campania_id, uId]
      );
    }
  }

  return dbObtenerCampaniaPorId(campania_id);
}

export async function dbActualizarCampania(
  id,
  {
    nombre,
    descripcion,
    fecha_inicio,
    fecha_fin,
    instrumento_id,
    version_instrumento,
    activa,
    unidades_ids,
  }
) {
  const campos = [];
  const valores = [id];
  let idx = 2;

  if (nombre !== undefined) {
    campos.push(`nombre = $${idx++}`);
    valores.push(nombre);
  }
  if (descripcion !== undefined) {
    campos.push(`descripcion = $${idx++}`);
    valores.push(descripcion);
  }
  if (fecha_inicio !== undefined) {
    campos.push(`fecha_inicio = $${idx++}`);
    valores.push(fecha_inicio);
  }
  if (fecha_fin !== undefined) {
    campos.push(`fecha_fin = $${idx++}`);
    valores.push(fecha_fin);
  }
  if (instrumento_id !== undefined) {
    campos.push(`instrumento_id = $${idx++}`);
    valores.push(instrumento_id);
  }
  if (version_instrumento !== undefined) {
    campos.push(`version_instrumento = $${idx++}`);
    valores.push(Number(version_instrumento));
  }
  if (activa !== undefined) {
    campos.push(`activa = $${idx++}`);
    valores.push(Boolean(activa));
  }

  if (campos.length > 0) {
    await pgQuery(
      `UPDATE catalogo.campania
       SET ${campos.join(", ")}
       WHERE campania_id = $1`,
      valores
    );
  }

  if (Array.isArray(unidades_ids)) {
    await pgQuery(`DELETE FROM catalogo.campania_unidad WHERE campania_id = $1`, [id]);
    for (const uId of unidades_ids) {
      await pgQuery(
        `INSERT INTO catalogo.campania_unidad (campania_id, unidad_organizacional_id)
         VALUES ($1, $2)
         ON CONFLICT (campania_id, unidad_organizacional_id) DO NOTHING`,
        [id, uId]
      );
    }
  }

  return dbObtenerCampaniaPorId(id);
}

export async function dbEliminarCampaniaLogica(id) {
  const r = await pgQuery(
    `UPDATE catalogo.campania
     SET activa = FALSE
     WHERE campania_id = $1
     RETURNING campania_id, nombre, activa, fecha_actualizacion`,
    [id]
  );
  return r.rows[0] || null;
}
