/**
 * Capa de datos de catalog-service.
 *
 * Reescrita contra el esquema realmente entregado en db/esquema/01_esquema.sql.
 * La version original del Integrante 2 nombraba columnas que no existen
 * (`catalogo.reactivo.escala_min`, que vive en `version_instrumento`;
 * `catalogo.campania.activa`, que es `estado`;
 * `catalogo.reactivo_instrumento_version`, que es `reactivo_version`;
 * `archivo_plantilla`, que no esta en ninguna tabla) y omitia
 * `catalogo.instrumento.fuente_id`, que es NOT NULL con llave foranea. Se
 * conservan los nombres de las funciones exportadas y la forma de sus
 * resultados, de modo que la capa de servicios y los controladores siguen
 * funcionando sin cambios.
 *
 * Dos reglas se mantienen en todo el archivo:
 *   - Toda consulta va parametrizada. Ninguna concatena valores.
 *   - No hay DELETE sobre entidades, solo baja logica. Las unicas
 *     operaciones de borrado son sobre tablas de relacion
 *     (reactivo_version, campania_unidad), donde desasociar no destruye
 *     ni el catalogo ni el historico de respuestas.
 */
import { pgQuery } from "@bienestar/comun/postgres.js";

/** Normaliza los parametros de paginacion de un listado. */
function paginar(page, limit) {
  const numPage = Math.max(1, Number(page) || 1);
  const numLimit = Math.max(1, Math.min(100, Number(limit) || 10));
  return { numPage, numLimit, offset: (numPage - 1) * numLimit };
}

function sobre(rows, total, numPage, numLimit) {
  return {
    rows, total, page: numPage, limit: numLimit,
    totalPages: Math.ceil(total / numLimit) || 1,
  };
}

function booleano(v) {
  return String(v) === "true" || v === true;
}

// ============================================================================
// 1. UNIDADES ORGANIZACIONALES
// ============================================================================

const COLS_UNIDAD = `unidad_organizacional_id, nombre, descripcion, tipo,
            unidad_padre_id, nivel_jerarquico, plantilla_declarada, activa,
            fecha_creacion, fecha_actualizacion`;

export async function dbListarUnidades({ activa, nombre, tipo, unidad_padre_id, page = 1, limit = 10 } = {}) {
  const cond = [];
  const val = [];
  let i = 1;
  if (activa !== undefined && activa !== null && activa !== "") {
    cond.push(`activa = $${i++}`); val.push(booleano(activa));
  }
  if (nombre) { cond.push(`nombre ILIKE $${i++}`); val.push(`%${nombre}%`); }
  if (tipo) { cond.push(`tipo = $${i++}`); val.push(tipo); }
  if (unidad_padre_id) { cond.push(`unidad_padre_id = $${i++}`); val.push(unidad_padre_id); }
  const where = cond.length ? `WHERE ${cond.join(" AND ")}` : "";

  const t = await pgQuery(
    `SELECT count(*)::int AS total FROM organizacion.unidad_organizacional ${where}`, val);
  const { numPage, numLimit, offset } = paginar(page, limit);
  const r = await pgQuery(
    `SELECT ${COLS_UNIDAD} FROM organizacion.unidad_organizacional ${where}
      ORDER BY nombre ASC LIMIT $${i++} OFFSET $${i++}`,
    [...val, numLimit, offset]);
  return sobre(r.rows, t.rows[0]?.total || 0, numPage, numLimit);
}

export async function dbObtenerUnidadPorId(id) {
  const r = await pgQuery(
    `SELECT ${COLS_UNIDAD} FROM organizacion.unidad_organizacional
      WHERE unidad_organizacional_id = $1`, [id]);
  return r.rows[0] || null;
}

export async function dbCrearUnidad({
  unidad_organizacional_id, nombre, descripcion, tipo = "AREA",
  unidad_padre_id, nivel_jerarquico = 0, plantilla_declarada = 0, activa = true,
}) {
  const r = await pgQuery(
    `INSERT INTO organizacion.unidad_organizacional
        (unidad_organizacional_id, nombre, descripcion, tipo, unidad_padre_id,
         nivel_jerarquico, plantilla_declarada, activa)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
     RETURNING ${COLS_UNIDAD}`,
    [unidad_organizacional_id, nombre, descripcion || null, tipo,
     unidad_padre_id || null, Number(nivel_jerarquico),
     Number(plantilla_declarada), Boolean(activa)]);
  return r.rows[0];
}

export async function dbActualizarUnidad(id, datos = {}) {
  const permitidos = ["nombre", "descripcion", "tipo", "unidad_padre_id",
                      "nivel_jerarquico", "plantilla_declarada", "activa"];
  const campos = [];
  const val = [id];
  let i = 2;
  for (const c of permitidos) {
    if (datos[c] === undefined) continue;
    campos.push(`${c} = $${i++}`);
    if (c === "activa") val.push(Boolean(datos[c]));
    else if (c === "nivel_jerarquico" || c === "plantilla_declarada") val.push(Number(datos[c]));
    else val.push(datos[c] === "" ? null : datos[c]);
  }
  if (!campos.length) return dbObtenerUnidadPorId(id);
  const r = await pgQuery(
    `UPDATE organizacion.unidad_organizacional SET ${campos.join(", ")}
      WHERE unidad_organizacional_id = $1 RETURNING ${COLS_UNIDAD}`, val);
  return r.rows[0] || null;
}

export async function dbEliminarUnidadLogica(id) {
  const r = await pgQuery(
    `UPDATE organizacion.unidad_organizacional SET activa = FALSE
      WHERE unidad_organizacional_id = $1
      RETURNING unidad_organizacional_id, nombre, activa, fecha_actualizacion`, [id]);
  return r.rows[0] || null;
}

// ============================================================================
// 2. INSTRUMENTOS Y VERSIONES
// ============================================================================

const COLS_INSTRUMENTO = `instrumento_id, nombre, descripcion, tipo, fuente_id,
            activo, fecha_creacion, fecha_actualizacion`;
const COLS_VERSION = `instrumento_id, version, fecha_vigencia_desde,
            fecha_vigencia_hasta, escala_min, escala_max, publicada, activa,
            fecha_creacion, fecha_actualizacion`;

export async function dbListarInstrumentos({ activo, tipo, nombre, page = 1, limit = 10 } = {}) {
  const cond = [];
  const val = [];
  let i = 1;
  if (activo !== undefined && activo !== null && activo !== "") {
    cond.push(`activo = $${i++}`); val.push(booleano(activo));
  }
  if (tipo) { cond.push(`tipo = $${i++}`); val.push(tipo); }
  if (nombre) { cond.push(`nombre ILIKE $${i++}`); val.push(`%${nombre}%`); }
  const where = cond.length ? `WHERE ${cond.join(" AND ")}` : "";

  const t = await pgQuery(`SELECT count(*)::int AS total FROM catalogo.instrumento ${where}`, val);
  const { numPage, numLimit, offset } = paginar(page, limit);
  const r = await pgQuery(
    `SELECT ${COLS_INSTRUMENTO} FROM catalogo.instrumento ${where}
      ORDER BY nombre ASC LIMIT $${i++} OFFSET $${i++}`,
    [...val, numLimit, offset]);
  return sobre(r.rows, t.rows[0]?.total || 0, numPage, numLimit);
}

export async function dbObtenerInstrumentoPorId(id) {
  const r = await pgQuery(
    `SELECT ${COLS_INSTRUMENTO} FROM catalogo.instrumento WHERE instrumento_id = $1`, [id]);
  if (!r.rows[0]) return null;
  const v = await pgQuery(
    `SELECT ${COLS_VERSION} FROM catalogo.version_instrumento
      WHERE instrumento_id = $1 ORDER BY version DESC`, [id]);
  return { ...r.rows[0], versiones: v.rows };
}

export async function dbCrearInstrumento({
  instrumento_id, nombre, descripcion, tipo, fuente_id = "FA-AUTOREPORTE", activo = true,
}) {
  // fuente_id apunta a catalogo.fuente_autorizada, donde las fuentes de
  // vigilancia estan declaradas con autorizada = FALSE. Un instrumento no
  // puede alimentarse de una fuente prohibida ni por descuido: la llave
  // foranea obliga a nombrar una fuente y la validacion de abajo obliga a
  // que este autorizada.
  const fuente = await pgQuery(
    `SELECT fuente_id, autorizada, motivo FROM catalogo.fuente_autorizada WHERE fuente_id = $1`,
    [fuente_id]);
  if (fuente.rows[0] && fuente.rows[0].autorizada === false) {
    const e = new Error(
      `La fuente ${fuente_id} no esta autorizada: ${fuente.rows[0].motivo}`);
    e.code = "FUENTE_NO_AUTORIZADA";
    throw e;
  }
  const r = await pgQuery(
    `INSERT INTO catalogo.instrumento
        (instrumento_id, nombre, descripcion, tipo, fuente_id, activo)
     VALUES ($1,$2,$3,$4,$5,$6) RETURNING ${COLS_INSTRUMENTO}`,
    [instrumento_id, nombre, descripcion || null, tipo, fuente_id, Boolean(activo)]);
  return r.rows[0];
}

export async function dbActualizarInstrumento(id, datos = {}) {
  const permitidos = ["nombre", "descripcion", "tipo", "fuente_id", "activo"];
  const campos = [];
  const val = [id];
  let i = 2;
  for (const c of permitidos) {
    if (datos[c] === undefined) continue;
    campos.push(`${c} = $${i++}`);
    val.push(c === "activo" ? Boolean(datos[c]) : (datos[c] === "" ? null : datos[c]));
  }
  if (!campos.length) return dbObtenerInstrumentoPorId(id);
  const r = await pgQuery(
    `UPDATE catalogo.instrumento SET ${campos.join(", ")}
      WHERE instrumento_id = $1 RETURNING ${COLS_INSTRUMENTO}`, val);
  return r.rows[0] || null;
}

export async function dbEliminarInstrumentoLogico(id) {
  const r = await pgQuery(
    `UPDATE catalogo.instrumento SET activo = FALSE WHERE instrumento_id = $1
      RETURNING instrumento_id, nombre, activo, fecha_actualizacion`, [id]);
  return r.rows[0] || null;
}

export async function dbListarVersiones(instrumento_id, { activa } = {}) {
  const cond = ["instrumento_id = $1"];
  const val = [instrumento_id];
  let i = 2;
  if (activa !== undefined && activa !== null && activa !== "") {
    cond.push(`activa = $${i++}`); val.push(booleano(activa));
  }
  const r = await pgQuery(
    `SELECT ${COLS_VERSION} FROM catalogo.version_instrumento
      WHERE ${cond.join(" AND ")} ORDER BY version DESC`, val);
  return r.rows;
}

export async function dbObtenerVersion(instrumento_id, version) {
  const r = await pgQuery(
    `SELECT ${COLS_VERSION} FROM catalogo.version_instrumento
      WHERE instrumento_id = $1 AND version = $2`, [instrumento_id, Number(version)]);
  return r.rows[0] || null;
}

export async function dbCrearVersion({
  instrumento_id, version, fecha_vigencia_desde, fecha_vigencia_hasta,
  escala_min = 1, escala_max = 5, publicada = false, activa = true,
}) {
  const r = await pgQuery(
    `INSERT INTO catalogo.version_instrumento
        (instrumento_id, version, fecha_vigencia_desde, fecha_vigencia_hasta,
         escala_min, escala_max, publicada, activa)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING ${COLS_VERSION}`,
    [instrumento_id, Number(version), fecha_vigencia_desde,
     fecha_vigencia_hasta || null, Number(escala_min), Number(escala_max),
     Boolean(publicada), Boolean(activa)]);
  return r.rows[0];
}

export async function dbActualizarVersion(instrumento_id, version, datos = {}) {
  const permitidos = ["fecha_vigencia_desde", "fecha_vigencia_hasta",
                      "escala_min", "escala_max", "publicada", "activa"];
  const campos = [];
  const val = [instrumento_id, Number(version)];
  let i = 3;
  for (const c of permitidos) {
    if (datos[c] === undefined) continue;
    campos.push(`${c} = $${i++}`);
    if (c === "publicada" || c === "activa") val.push(Boolean(datos[c]));
    else if (c === "escala_min" || c === "escala_max") val.push(Number(datos[c]));
    else val.push(datos[c] === "" ? null : datos[c]);
  }
  if (!campos.length) return dbObtenerVersion(instrumento_id, version);
  const r = await pgQuery(
    `UPDATE catalogo.version_instrumento SET ${campos.join(", ")}
      WHERE instrumento_id = $1 AND version = $2 RETURNING ${COLS_VERSION}`, val);
  return r.rows[0] || null;
}

export async function dbEliminarVersionLogica(instrumento_id, version) {
  const r = await pgQuery(
    `UPDATE catalogo.version_instrumento SET activa = FALSE
      WHERE instrumento_id = $1 AND version = $2
      RETURNING instrumento_id, version, activa, fecha_actualizacion`,
    [instrumento_id, Number(version)]);
  return r.rows[0] || null;
}

// ============================================================================
// 3. REACTIVOS Y SU VINCULACION A VERSIONES
// ============================================================================

const COLS_REACTIVO = `reactivo_id, texto, dimension_id, invertido, activo,
            fecha_creacion, fecha_actualizacion`;

export async function dbListarReactivos({ activo, dimension_id, texto, page = 1, limit = 10 } = {}) {
  const cond = [];
  const val = [];
  let i = 1;
  if (activo !== undefined && activo !== null && activo !== "") {
    cond.push(`activo = $${i++}`); val.push(booleano(activo));
  }
  if (dimension_id) { cond.push(`dimension_id = $${i++}`); val.push(dimension_id); }
  if (texto) { cond.push(`texto ILIKE $${i++}`); val.push(`%${texto}%`); }
  const where = cond.length ? `WHERE ${cond.join(" AND ")}` : "";

  const t = await pgQuery(`SELECT count(*)::int AS total FROM catalogo.reactivo ${where}`, val);
  const { numPage, numLimit, offset } = paginar(page, limit);
  const r = await pgQuery(
    `SELECT ${COLS_REACTIVO} FROM catalogo.reactivo ${where}
      ORDER BY reactivo_id ASC LIMIT $${i++} OFFSET $${i++}`,
    [...val, numLimit, offset]);
  return sobre(r.rows, t.rows[0]?.total || 0, numPage, numLimit);
}

export async function dbObtenerReactivoPorId(id) {
  const r = await pgQuery(
    `SELECT ${COLS_REACTIVO} FROM catalogo.reactivo WHERE reactivo_id = $1`, [id]);
  return r.rows[0] || null;
}

export async function dbCrearReactivo({
  reactivo_id, texto, dimension_id, invertido = false, activo = true,
}) {
  // La escala NO es del reactivo sino de la version del instrumento: dos
  // versiones del mismo instrumento pueden usar escalas distintas y el
  // mecanismo de privacidad diferencial lee el rango de ahi para recortar.
  const r = await pgQuery(
    `INSERT INTO catalogo.reactivo (reactivo_id, texto, dimension_id, invertido, activo)
     VALUES ($1,$2,$3,$4,$5) RETURNING ${COLS_REACTIVO}`,
    [reactivo_id, texto, dimension_id, Boolean(invertido), Boolean(activo)]);
  return r.rows[0];
}

export async function dbActualizarReactivo(id, datos = {}) {
  const permitidos = ["texto", "dimension_id", "invertido", "activo"];
  const campos = [];
  const val = [id];
  let i = 2;
  for (const c of permitidos) {
    if (datos[c] === undefined) continue;
    campos.push(`${c} = $${i++}`);
    val.push(c === "invertido" || c === "activo" ? Boolean(datos[c]) : datos[c]);
  }
  if (!campos.length) return dbObtenerReactivoPorId(id);
  const r = await pgQuery(
    `UPDATE catalogo.reactivo SET ${campos.join(", ")}
      WHERE reactivo_id = $1 RETURNING ${COLS_REACTIVO}`, val);
  return r.rows[0] || null;
}

export async function dbEliminarReactivoLogico(id) {
  const r = await pgQuery(
    `UPDATE catalogo.reactivo SET activo = FALSE WHERE reactivo_id = $1
      RETURNING reactivo_id, texto, activo, fecha_actualizacion`, [id]);
  return r.rows[0] || null;
}

export async function dbListarReactivosDeVersion(instrumento_id, version) {
  const r = await pgQuery(
    `SELECT r.reactivo_id, r.texto, r.dimension_id, r.invertido, r.activo,
            rv.orden, rv.obligatorio, vi.escala_min, vi.escala_max
       FROM catalogo.reactivo_version rv
       JOIN catalogo.reactivo r            ON r.reactivo_id = rv.reactivo_id
       JOIN catalogo.version_instrumento vi
            ON vi.instrumento_id = rv.instrumento_id AND vi.version = rv.version
      WHERE rv.instrumento_id = $1 AND rv.version = $2 AND r.activo
      ORDER BY rv.orden ASC`,
    [instrumento_id, Number(version)]);
  return r.rows;
}

export async function dbAsociarReactivoAVersion(instrumento_id, version, { reactivo_id, orden, obligatorio = true }) {
  const r = await pgQuery(
    `INSERT INTO catalogo.reactivo_version
        (instrumento_id, version, reactivo_id, orden, obligatorio)
     VALUES ($1,$2,$3,$4,$5)
     ON CONFLICT (instrumento_id, version, reactivo_id)
     DO UPDATE SET orden = EXCLUDED.orden, obligatorio = EXCLUDED.obligatorio
     RETURNING instrumento_id, version, reactivo_id, orden, obligatorio`,
    [instrumento_id, Number(version), reactivo_id, Number(orden), Boolean(obligatorio)]);
  return r.rows[0];
}

export async function dbDesasociarReactivoDeVersion(instrumento_id, version, reactivo_id) {
  const r = await pgQuery(
    `DELETE FROM catalogo.reactivo_version
      WHERE instrumento_id = $1 AND version = $2 AND reactivo_id = $3
      RETURNING instrumento_id, version, reactivo_id`,
    [instrumento_id, Number(version), reactivo_id]);
  return r.rows[0] || null;
}

// ============================================================================
// 4. CAMPANIAS Y SU ASIGNACION A UNIDADES
// ============================================================================

const COLS_CAMPANIA = `campania_id, nombre, instrumento_id, version_instrumento,
            fecha_inicio, fecha_fin, estado, secuencia,
            fecha_creacion, fecha_actualizacion`;

export async function dbListarCampanias({
  estado, instrumento_id, unidad_organizacional_id, page = 1, limit = 10 } = {}) {
  const cond = [];
  const val = [];
  let i = 1;
  if (estado) { cond.push(`c.estado = $${i++}`); val.push(estado); }
  if (instrumento_id) { cond.push(`c.instrumento_id = $${i++}`); val.push(instrumento_id); }
  if (unidad_organizacional_id) {
    cond.push(`EXISTS (SELECT 1 FROM catalogo.campania_unidad cu
                        WHERE cu.campania_id = c.campania_id
                          AND cu.unidad_organizacional_id = $${i++})`);
    val.push(unidad_organizacional_id);
  }
  const where = cond.length ? `WHERE ${cond.join(" AND ")}` : "";

  const t = await pgQuery(
    `SELECT count(*)::int AS total FROM catalogo.campania c ${where}`, val);
  const { numPage, numLimit, offset } = paginar(page, limit);
  const r = await pgQuery(
    `SELECT ${COLS_CAMPANIA.split(",").map((c) => `c.${c.trim()}`).join(", ")}
       FROM catalogo.campania c ${where}
      ORDER BY c.secuencia DESC, c.fecha_inicio DESC
      LIMIT $${i++} OFFSET $${i++}`,
    [...val, numLimit, offset]);
  return sobre(r.rows, t.rows[0]?.total || 0, numPage, numLimit);
}

export async function dbObtenerCampaniaPorId(id) {
  const r = await pgQuery(
    `SELECT ${COLS_CAMPANIA} FROM catalogo.campania WHERE campania_id = $1`, [id]);
  if (!r.rows[0]) return null;
  const u = await pgQuery(
    `SELECT cu.unidad_organizacional_id, uo.nombre
       FROM catalogo.campania_unidad cu
       JOIN organizacion.unidad_organizacional uo USING (unidad_organizacional_id)
      WHERE cu.campania_id = $1 ORDER BY uo.nombre`, [id]);
  return { ...r.rows[0], unidades: u.rows };
}

export async function dbCrearCampania({
  campania_id, nombre, fecha_inicio, fecha_fin, instrumento_id,
  version_instrumento, estado = "BORRADOR", secuencia, unidades_ids = [],
}) {
  // La campania y sus unidades se escriben en UNA transaccion. Si falla la
  // asignacion de unidades, no debe quedar una campania sin alcance: una
  // campania sin unidades no le llega a nadie y es indistinguible de un
  // error de captura.
  const { enTransaccion } = await import("@bienestar/comun/postgres.js");
  await enTransaccion(async (cliente) => {
    let sec = secuencia;
    if (sec === undefined || sec === null || sec === "") {
      const s = await cliente.query(
        `SELECT COALESCE(MAX(secuencia), 0) + 1 AS siguiente FROM catalogo.campania`);
      sec = s.rows[0].siguiente;
    }
    await cliente.query(
      `INSERT INTO catalogo.campania
          (campania_id, nombre, instrumento_id, version_instrumento,
           fecha_inicio, fecha_fin, estado, secuencia)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`,
      [campania_id, nombre, instrumento_id, Number(version_instrumento),
       fecha_inicio, fecha_fin, estado, Number(sec)]);
    for (const uId of (Array.isArray(unidades_ids) ? unidades_ids : [])) {
      await cliente.query(
        `INSERT INTO catalogo.campania_unidad (campania_id, unidad_organizacional_id)
         VALUES ($1,$2) ON CONFLICT DO NOTHING`, [campania_id, uId]);
    }
  });
  return dbObtenerCampaniaPorId(campania_id);
}

export async function dbActualizarCampania(id, datos = {}) {
  const permitidos = ["nombre", "fecha_inicio", "fecha_fin", "estado",
                      "instrumento_id", "version_instrumento", "secuencia"];
  const campos = [];
  const val = [id];
  let i = 2;
  for (const c of permitidos) {
    if (datos[c] === undefined) continue;
    campos.push(`${c} = $${i++}`);
    val.push(c === "version_instrumento" || c === "secuencia" ? Number(datos[c]) : datos[c]);
  }
  if (campos.length) {
    await pgQuery(
      `UPDATE catalogo.campania SET ${campos.join(", ")} WHERE campania_id = $1`, val);
  }
  if (Array.isArray(datos.unidades_ids)) {
    await pgQuery(`DELETE FROM catalogo.campania_unidad WHERE campania_id = $1`, [id]);
    for (const uId of datos.unidades_ids) {
      await pgQuery(
        `INSERT INTO catalogo.campania_unidad (campania_id, unidad_organizacional_id)
         VALUES ($1,$2) ON CONFLICT DO NOTHING`, [id, uId]);
    }
  }
  return dbObtenerCampaniaPorId(id);
}

/**
 * Baja logica de una campania: pasa a CANCELADA.
 *
 * Una campania CERRADA ya no admite respuestas pero sus agregados siguen
 * publicados; CANCELADA significa que no debe considerarse en la
 * tendencia. Son dos cosas distintas y por eso no se usa una sola bandera.
 * Una campania que ya tiene respuestas no se cancela: eso borraria de la
 * tendencia una medicion que la gente si contesto.
 */
export async function dbEliminarCampaniaLogica(id) {
  const r = await pgQuery(
    `UPDATE catalogo.campania SET estado = 'CANCELADA'
      WHERE campania_id = $1 AND estado IN ('BORRADOR','ABIERTA')
      RETURNING campania_id, nombre, estado, fecha_actualizacion`, [id]);
  return r.rows[0] || null;
}

export async function dbListarDimensiones() {
  const r = await pgQuery(
    `SELECT dimension_id, nombre, descripcion, orden
       FROM catalogo.dimension ORDER BY orden, nombre`);
  return r.rows;
}

export async function dbListarFuentes() {
  const r = await pgQuery(
    `SELECT fuente_id, nombre, descripcion, autorizada, motivo
       FROM catalogo.fuente_autorizada ORDER BY autorizada DESC, nombre`);
  return r.rows;
}

export async function dbListarParametros() {
  const r = await pgQuery(
    `SELECT clave, valor, unidad, descripcion, justificacion, actualizado_por, fecha_actualizacion
       FROM agregado.parametro_privacidad ORDER BY clave`);
  return r.rows;
}
