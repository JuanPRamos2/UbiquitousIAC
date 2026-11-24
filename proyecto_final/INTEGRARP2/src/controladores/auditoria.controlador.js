import * as Bitacora from "../modelos/Bitacora.js";
import * as Consentimiento from "../servicios/consentimiento.servicio.js";
import * as Portal from "../servicios/portal.servicio.js";
import { asyncHandler } from "../utilidades/errores.js";

export const listar = asyncHandler(async (req, res) => {
  const data = await Bitacora.listarBitacora({ limite: req.query.limite });
  res.json({
    data: data.map((row) => ({
      actor_id: row.actor_id,
      actor_perfil: row.actor_perfil,
      accion: row.accion,
      recurso: row.recurso,
      resultado: row.resultado,
      correlacion_id: row.correlacion_id,
      timestamp: row.timestamp,
    })),
  });
});

export const historialConsentimiento = asyncHandler(async (req, res) => {
  res.json(
    await Consentimiento.historialPorSeudonimo({
      actor: req.actor,
      seudonimoId: req.params.seudonimoId,
      correlacionId: req.correlacionId,
    })
  );
});

export const listarSoporte = asyncHandler(async (_req, res) => {
  res.json(await Portal.listarApoyo());
});

export const listarEvidenciaConsentimiento = asyncHandler(async (_req, res) => {
  res.json(await Consentimiento.listarEvidencia());
});
