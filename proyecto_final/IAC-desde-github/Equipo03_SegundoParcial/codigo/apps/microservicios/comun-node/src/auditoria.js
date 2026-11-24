/**
 * Registro de eventos en auditoria.bitacora desde microservicios en Node.js.
 *
 * Registra acciones completadas, rechazos por permisos o umbrales insuficientes.
 * Si la escritura en la base de datos relacional falla, nunca rompe la transaccion
 * del usuario para mantener la disponibilidad del servicio.
 */
import { ejecutar } from "./postgres.js";

export async function registrarBitacora(req, accion, resultado = "EXITO", { tipo_recurso = null, recurso_id = null } = {}) {
  const actor = req?.actor || {};
  const actorId = actor.sub || actor.usuario_id || null;
  const actorPerfil = actor.perfil || "ANONIMO";
  const correlacion = req?.correlacionId || "";

  let ip = req?.headers?.["x-forwarded-for"] || req?.socket?.remoteAddress || null;
  if (ip && ip.includes(",")) {
    ip = ip.split(",")[0].trim();
  }
  // Sanear direccion IPv6 mapeada a IPv4 (ej. ::ffff:127.0.0.1)
  if (ip && ip.startsWith("::ffff:")) {
    ip = ip.replace("::ffff:", "");
  }
  if (ip === "::1") {
    ip = "127.0.0.1";
  }

  try {
    await ejecutar(
      `INSERT INTO auditoria.bitacora
         (actor_usuario_id, actor_perfil, accion, tipo_recurso, recurso_id,
          resultado, correlacion_id, direccion_origen)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8::inet)`,
      [
        actorId,
        actorPerfil.slice(0, 30),
        accion,
        tipo_recurso,
        recurso_id ? String(recurso_id).slice(0, 80) : null,
        resultado,
        correlacion,
        ip,
      ]
    );
  } catch (err) {
    // Falla controlada: se emite log tecnico pero no tumba la solicitud del cliente
    console.error(`[AUDITORIA] No se pudo registrar bitacora (${accion} / ${resultado}):`, err.message);
  }
}
