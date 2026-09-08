import { pgQuery } from "../config/postgres.js";

export async function buscarUsuarioPorCorreo(correo) {
  const r = await pgQuery(
    `SELECT u.usuario_id, u.activo, u.correo, u.nombre, u.apellido_paterno, p.codigo AS perfil
     FROM usuarios.usuario u
     JOIN usuarios.usuario_perfil up
       ON up.usuario_id = u.usuario_id AND up.perfil_principal = TRUE
     JOIN usuarios.perfil p ON p.perfil_id = up.perfil_id AND p.activo = TRUE
     WHERE lower(u.correo) = lower($1)`,
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
    `SELECT u.usuario_id, u.nombre, u.apellido_paterno, p.codigo AS perfil
     FROM usuarios.usuario u
     JOIN usuarios.usuario_perfil up
       ON up.usuario_id = u.usuario_id AND up.perfil_principal = TRUE
     JOIN usuarios.perfil p ON p.perfil_id = up.perfil_id
     WHERE u.usuario_id = $1 AND u.activo = TRUE AND p.activo = TRUE`,
    [usuarioId]
  );
  return r.rows[0] || null;
}

export async function contextoOperativo(usuarioId) {
  const r = await pgQuery(
    `SELECT e.unidad_organizacional_id,
            s.seudonimo_id
     FROM usuarios.empleado e
     LEFT JOIN consentimiento.seudonimo s
       ON s.empleado_id = e.empleado_id AND s.activo = TRUE
     WHERE e.usuario_id = $1 AND e.activo = TRUE`,
    [usuarioId]
  );
  return r.rows[0] || null;
}

export async function listarCuentas() {
  const r = await pgQuery(
    `SELECT u.usuario_id, u.correo, u.activo, u.fecha_ultimo_acceso,
            p.codigo AS perfil, p.nombre AS perfil_nombre, p.nivel_acceso
     FROM usuarios.usuario u
     JOIN usuarios.usuario_perfil up
       ON up.usuario_id = u.usuario_id AND up.perfil_principal = TRUE
     JOIN usuarios.perfil p ON p.perfil_id = up.perfil_id
     ORDER BY p.nivel_acceso, u.correo`
  );
  return r.rows;
}

export async function listarPerfiles() {
  const r = await pgQuery(
    `SELECT codigo, nombre, nivel_acceso, activo
     FROM usuarios.perfil
     ORDER BY nivel_acceso`
  );
  return r.rows;
}
