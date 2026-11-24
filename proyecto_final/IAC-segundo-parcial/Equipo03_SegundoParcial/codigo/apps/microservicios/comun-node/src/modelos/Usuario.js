/**
 * Contexto operativo de un usuario, leido de PostgreSQL.
 *
 * Devuelve el seudonimo de la persona, nunca su empleado_id: es lo unico
 * que los microservicios de proceso necesitan y lo unico que puede viajar
 * a MongoDB.
 *
 * La consulta pasa por portal.v_participacion_propia y NO por la tabla
 * consentimiento.seudonimo. El rol de la aplicacion no tiene permiso de
 * lectura sobre esa tabla a proposito: poder recorrer la correspondencia
 * completa entre personas y seudonimos seria exactamente lo que el
 * proyecto promete que nadie puede hacer. La vista entrega una fila por
 * usuario y se consulta siempre con WHERE usuario_id = <el de la sesion>.
 */
import { consultarUno } from "../postgres.js";

export async function contextoOperativo(usuarioId) {
  if (!usuarioId) return null;
  const participacion = await consultarUno(
    `SELECT usuario_id, seudonimo_id, estado_consentimiento, campanias_respondidas
       FROM portal.v_participacion_propia
      WHERE usuario_id = $1`,
    [usuarioId]
  );
  if (!participacion) return null;
  // La unidad se lee del padron de empleados, que el rol si puede leer y
  // que no revela ninguna correspondencia con seudonimos.
  const unidad = await consultarUno(
    `SELECT unidad_organizacional_id
       FROM usuarios.empleado
      WHERE usuario_id = $1 AND activo`,
    [usuarioId]
  );
  return {
    ...participacion,
    unidad_organizacional_id: unidad?.unidad_organizacional_id || null,
  };
}

/** Datos de la cuenta, sin tocar identidad laboral. */
export async function cuenta(usuarioId) {
  return consultarUno(
    `SELECT u.usuario_id, u.correo, u.nombre, u.apellido_paterno, u.activo
       FROM usuarios.usuario u
      WHERE u.usuario_id = $1`,
    [usuarioId]
  );
}
