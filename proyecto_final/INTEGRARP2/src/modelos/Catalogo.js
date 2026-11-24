import { pgQuery, pgTransaction } from "../config/postgres.js";

const CAMPANIA_COLS = `
  campania_id, nombre, fecha_inicio, fecha_fin,
  instrumento_id, version_instrumento, estado,
  (estado = 'ABIERTA') AS activa
`;

export async function listarUnidades() {
  const r = await pgQuery(
    `SELECT unidad_organizacional_id, nombre, unidad_padre_id, nivel_jerarquico
     FROM organizacion.unidad_organizacional
     WHERE activa = TRUE
     ORDER BY nombre`
  );
  return r.rows;
}

export async function listarCampanias() {
  const r = await pgQuery(
    `SELECT ${CAMPANIA_COLS}
     FROM catalogo.campania
     ORDER BY secuencia DESC, fecha_inicio DESC`
  );
  return r.rows;
}

export async function listarInstrumentos() {
  const r = await pgQuery(
    `SELECT instrumento_id, nombre, tipo, activo
     FROM catalogo.instrumento
     WHERE activo = TRUE
     ORDER BY nombre`
  );
  return r.rows;
}

export async function listarCampaniasDeUnidad(unidadId, { soloAbiertas = false } = {}) {
  const r = await pgQuery(
    `SELECT c.campania_id, c.nombre, c.fecha_inicio, c.fecha_fin,
            c.instrumento_id, c.version_instrumento, c.estado,
            (c.estado = 'ABIERTA') AS activa
     FROM catalogo.campania c
     JOIN catalogo.campania_unidad cu ON cu.campania_id = c.campania_id
     WHERE cu.unidad_organizacional_id = $1
       AND ($2::boolean = FALSE OR c.estado = 'ABIERTA')
     ORDER BY c.secuencia DESC, c.fecha_inicio DESC`,
    [unidadId, soloAbiertas]
  );
  return r.rows;
}

export async function obtenerCampania(campaniaId) {
  const r = await pgQuery(
    `SELECT ${CAMPANIA_COLS}
     FROM catalogo.campania
     WHERE campania_id = $1`,
    [campaniaId]
  );
  return r.rows[0] || null;
}

export async function campaniaAsignadaAUnidad(campaniaId, unidadId) {
  const r = await pgQuery(
    `SELECT 1 FROM catalogo.campania_unidad
     WHERE campania_id = $1 AND unidad_organizacional_id = $2`,
    [campaniaId, unidadId]
  );
  return r.rowCount === 1;
}

export async function reactivosDeVersion(instrumentoId, version) {
  const r = await pgQuery(
    `SELECT r.reactivo_id, r.texto, d.nombre AS dimension,
            vi.escala_min, vi.escala_max, r.invertido, rv.orden, rv.obligatorio
     FROM catalogo.reactivo_version rv
     JOIN catalogo.reactivo r ON r.reactivo_id = rv.reactivo_id AND r.activo = TRUE
     JOIN catalogo.dimension d ON d.dimension_id = r.dimension_id
     JOIN catalogo.version_instrumento vi
       ON vi.instrumento_id = rv.instrumento_id AND vi.version = rv.version
     WHERE rv.instrumento_id = $1 AND rv.version = $2
     ORDER BY rv.orden`,
    [instrumentoId, version]
  );
  return r.rows;
}

export async function listarDimensiones() {
  const r = await pgQuery(
    `SELECT dimension_id, nombre FROM catalogo.dimension ORDER BY orden, nombre`
  );
  return r.rows;
}

export async function obtenerSeudonimo(seudonimoId) {
  const r = await pgQuery(
    `SELECT s.seudonimo_id, s.activo,
            e.unidad_organizacional_id, e.usuario_id
     FROM consentimiento.seudonimo s
     JOIN usuarios.empleado e ON e.empleado_id = s.empleado_id
     WHERE s.seudonimo_id = $1`,
    [seudonimoId]
  );
  return r.rows[0] || null;
}

export async function consentimientoVigente(seudonimoId) {
  const r = await pgQuery(
    `SELECT seudonimo_id, aviso_id AS version_consentimiento_id, estado
     FROM consentimiento.v_estado_vigente
     WHERE seudonimo_id = $1 AND estado = 'ACEPTADO'`,
    [seudonimoId]
  );
  return r.rows[0] || null;
}

export async function historialConsentimiento(seudonimoId) {
  const r = await pgQuery(
    `SELECT c.seudonimo_id,
            c.aviso_id AS version_consentimiento_id,
            c.fecha_evento AS fecha_aceptacion,
            NULL::timestamptz AS fecha_revocacion,
            c.estado
     FROM consentimiento.consentimiento c
     WHERE c.seudonimo_id = $1
     ORDER BY c.fecha_evento DESC`,
    [seudonimoId]
  );
  return r.rows;
}

export async function existeSeudonimo(seudonimoId) {
  const r = await pgQuery(
    `SELECT 1 FROM consentimiento.seudonimo WHERE seudonimo_id = $1`,
    [seudonimoId]
  );
  return r.rowCount === 1;
}

let cacheCodigosAuditoria = null;

export async function validarCodigosAuditoria({ accion, resultado }) {
  if (!cacheCodigosAuditoria) {
    const [acciones, resultados] = await Promise.all([
      pgQuery("SELECT codigo FROM auditoria.tipo_accion"),
      pgQuery("SELECT codigo FROM auditoria.resultado"),
    ]);
    cacheCodigosAuditoria = {
      accion: new Set(acciones.rows.map((row) => row.codigo)),
      resultado: new Set(resultados.rows.map((row) => row.codigo)),
    };
  }
  return {
    accion_ok: cacheCodigosAuditoria.accion.has(accion),
    resultado_ok: cacheCodigosAuditoria.resultado.has(resultado),
  };
}

export async function leerUmbralK() {
  const r = await pgQuery(
    `SELECT valor FROM agregado.parametro_privacidad WHERE clave = 'k_umbral_minimo'`
  );
  return Number(r.rows[0]?.valor || 5);
}

export async function leerParametros() {
  const [parametros, aviso] = await Promise.all([
    pgQuery(`SELECT clave, valor FROM agregado.parametro_privacidad`),
    pgQuery(
      `SELECT aviso_id FROM consentimiento.aviso_privacidad WHERE vigente = TRUE LIMIT 1`
    ),
  ]);
  const map = Object.fromEntries(parametros.rows.map((row) => [row.clave, row.valor]));
  map.k = Number(map.k_umbral_minimo || 5);
  map.version_activa_consentimiento = aviso.rows[0]?.aviso_id || null;
  return map;
}

export async function actualizarUmbralK(valor, usuarioId) {
  await pgQuery(
    `UPDATE agregado.parametro_privacidad
     SET valor = $1, fecha_actualizacion = NOW(), actualizado_por = $2
     WHERE clave = 'k_umbral_minimo'`,
    [valor, usuarioId]
  );
}

export async function listarVersionesConsentimiento() {
  const r = await pgQuery(
    `SELECT aviso_id AS version_consentimiento_id,
            version AS resumen_cambios,
            fecha_vigencia,
            vigente AS activo
     FROM consentimiento.aviso_privacidad
     ORDER BY fecha_vigencia DESC`
  );
  return r.rows;
}

export async function listarConsentimientos() {
  const r = await pgQuery(
    `SELECT seudonimo_id,
            aviso_id AS version_consentimiento_id,
            fecha_evento AS fecha_aceptacion,
            NULL::timestamptz AS fecha_revocacion,
            estado
     FROM consentimiento.v_estado_vigente
     ORDER BY fecha_evento DESC
     LIMIT 100`
  );
  return r.rows;
}

export async function revocarConsentimientosVigentes(seudonimoId) {
  const r = await pgQuery(
    `INSERT INTO consentimiento.consentimiento (seudonimo_id, aviso_id, estado, fecha_evento)
     SELECT seudonimo_id, aviso_id, 'REVOCADO', NOW()
     FROM consentimiento.v_estado_vigente
     WHERE seudonimo_id = $1 AND estado = 'ACEPTADO'`,
    [seudonimoId]
  );
  return r.rowCount;
}

export async function aceptarConsentimiento(seudonimoId, avisoId) {
  await pgQuery(
    `INSERT INTO consentimiento.consentimiento (seudonimo_id, aviso_id, estado, fecha_evento)
     VALUES ($1, $2, 'ACEPTADO', NOW())`,
    [seudonimoId, avisoId]
  );
}

export async function activarAviso(avisoId) {
  await pgTransaction(async (query) => {
    await query(`UPDATE consentimiento.aviso_privacidad SET vigente = FALSE WHERE vigente = TRUE`);
    const r = await query(
      `UPDATE consentimiento.aviso_privacidad SET vigente = TRUE WHERE aviso_id = $1`,
      [avisoId]
    );
    if (r.rowCount !== 1) {
      throw new Error("AVISO_INVALIDO");
    }
  });
}

export async function calcularAgregadoProtegido({ campaniaId, unidadId, dimensionId, actorId }) {
  const r = await pgQuery(
    `SELECT estado, n, valor_protegido, epsilon, escala_ruido, mensaje
     FROM agregado.fn_calcular_agregado_protegido($1, $2, $3, $4)`,
    [campaniaId, unidadId, dimensionId, actorId]
  );
  return r.rows[0] || null;
}
