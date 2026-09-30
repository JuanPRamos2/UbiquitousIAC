import { pgQuery } from "../config/postgres.js";
import { validarCodigosAuditoria } from "./Catalogo.js";

export async function registrarBitacora(doc) {
  const chequeo = await validarCodigosAuditoria({
    accion: doc.accion,
    resultado: doc.resultado,
  });
  if (!chequeo.accion_ok || !chequeo.resultado_ok) {
    throw new Error(
      `Código de auditoría fuera de catálogo PostgreSQL: accion=${doc.accion} resultado=${doc.resultado}`
    );
  }

  const actorId = doc.actor_id && doc.actor_id !== "DESCONOCIDO" ? doc.actor_id : null;
  await pgQuery(
    `INSERT INTO auditoria.bitacora
       (actor_usuario_id, actor_perfil, accion, tipo_recurso, recurso_id, resultado, correlacion_id)
     VALUES ($1, $2, $3, $4, $5, $6, $7)`,
    [
      actorId,
      doc.actor_perfil || "DESCONOCIDO",
      doc.accion,
      doc.recurso || null,
      doc.recurso_id || null,
      doc.resultado,
      doc.correlacion_id || "sin-correlacion",
    ]
  );
}

export async function listarBitacora({ limite = 50 } = {}) {
  const r = await pgQuery(
    `SELECT actor_usuario_id AS actor_id,
            actor_perfil,
            accion,
            COALESCE(recurso_id, tipo_recurso) AS recurso,
            resultado,
            correlacion_id,
            fecha_hora AS timestamp
     FROM auditoria.bitacora
     ORDER BY fecha_hora DESC
     LIMIT $1`,
    [Math.min(Number(limite) || 50, 200)]
  );
  return r.rows;
}

export async function listarAccesosPropios(usuarioId, { limite = 50 } = {}) {
  const r = await pgQuery(
    `SELECT NULL::varchar AS actor_id,
            actor_perfil,
            que_hizo AS accion,
            'CONSENTIMIENTO' AS recurso,
            resultado,
            NULL::varchar AS correlacion_id,
            fecha_hora AS timestamp
     FROM portal.v_accesos_a_mis_datos
     WHERE usuario_id = $1
     ORDER BY fecha_hora DESC
     LIMIT $2`,
    [usuarioId, Math.min(Number(limite) || 50, 200)]
  );
  return r.rows;
}
