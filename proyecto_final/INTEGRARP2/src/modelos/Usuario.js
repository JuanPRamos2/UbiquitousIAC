import { pgQuery } from "../config/postgres.js";

const PERFIL_JOIN = `
  JOIN usuarios.usuario_perfil up ON up.usuario_id = u.usuario_id
  JOIN usuarios.perfil p ON p.perfil_id = up.perfil_id AND p.activo = TRUE
`;

export async function buscarUsuarioPorCorreo(correo) {
  const r = await pgQuery(
    `SELECT DISTINCT ON (u.usuario_id)
            u.usuario_id, u.activo, u.correo, u.nombre, u.apellido_paterno, p.codigo AS perfil
     FROM usuarios.usuario u
     ${PERFIL_JOIN}
     WHERE lower(u.correo) = lower($1)
     ORDER BY u.usuario_id, up.fecha_asignacion`,
    [correo]
  );
  return r.rows[0] || null;
}

export async function verificarContrasena(usuarioId, contrasena) {
  const r = await pgQuery(
    `SELECT 1
     FROM usuarios.usuario
     WHERE usuario_id = $1
       AND activo = TRUE
       AND contrasena_hash = crypt($2, contrasena_hash)`,
    [usuarioId, contrasena]
  );
  return r.rowCount === 1;
}

export async function marcarUltimoAcceso(usuarioId) {
  await pgQuery(
    `UPDATE usuarios.usuario SET fecha_ultimo_acceso = NOW() WHERE usuario_id = $1`,
    [usuarioId]
  );
}

export async function perfilDeUsuario(usuarioId) {
  const r = await pgQuery(
    `SELECT DISTINCT ON (u.usuario_id)
            u.usuario_id, u.nombre, u.apellido_paterno, p.codigo AS perfil
     FROM usuarios.usuario u
     ${PERFIL_JOIN}
     WHERE u.usuario_id = $1 AND u.activo = TRUE
     ORDER BY u.usuario_id, up.fecha_asignacion`,
    [usuarioId]
  );
  return r.rows[0] || null;
}

export async function contextoOperativo(usuarioId) {
  const r = await pgQuery(
    `SELECT COALESCE(e.unidad_organizacional_id, up.unidad_alcance_id) AS unidad_organizacional_id,
            s.seudonimo_id
     FROM usuarios.usuario u
     LEFT JOIN usuarios.usuario_perfil up ON up.usuario_id = u.usuario_id
     LEFT JOIN usuarios.empleado e ON e.usuario_id = u.usuario_id AND e.activo = TRUE
     LEFT JOIN consentimiento.seudonimo s
       ON s.empleado_id = e.empleado_id AND s.activo = TRUE
     WHERE u.usuario_id = $1
     ORDER BY up.fecha_asignacion
     LIMIT 1`,
    [usuarioId]
  );
  return r.rows[0] || null;
}

export async function listarCuentas() {
  const r = await pgQuery(
    `SELECT DISTINCT ON (u.usuario_id)
            u.usuario_id, u.correo, u.activo, u.fecha_ultimo_acceso,
            p.codigo AS perfil, p.nombre AS perfil_nombre, p.descripcion
     FROM usuarios.usuario u
     ${PERFIL_JOIN}
     ORDER BY u.usuario_id, up.fecha_asignacion`
  );
  return r.rows;
}

export async function listarPerfiles() {
  const r = await pgQuery(
    `SELECT codigo, nombre, descripcion, activo
     FROM usuarios.perfil
     ORDER BY perfil_id`
  );
  return r.rows;
}
