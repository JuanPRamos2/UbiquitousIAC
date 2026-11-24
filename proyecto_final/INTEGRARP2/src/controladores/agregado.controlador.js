import * as Agregado from "../servicios/agregado.servicio.js";
import { asyncHandler } from "../utilidades/errores.js";

export const consultar = asyncHandler(async (req, res) => {
  const out = await Agregado.consultarAgregado({
    actor: req.actor,
    unidadId: req.params.unidadId,
    campaniaId: req.params.campaniaId,
    correlacionId: req.correlacionId,
  });
  res.json(out);
});

export const leerK = asyncHandler(async (_req, res) => {
  res.json(await Agregado.leerK());
});

export const cambiarK = asyncHandler(async (req, res) => {
  res.json(
    await Agregado.cambiarK({
      actor: req.actor,
      k: req.body?.k,
      correlacionId: req.correlacionId,
    })
  );
});

export const leerParametros = asyncHandler(async (_req, res) => {
  res.json(await Agregado.leerParametros());
});

export const guardarParametros = asyncHandler(async (req, res) => {
  res.json(
    await Agregado.guardarParametros({
      actor: req.actor,
      k: req.body?.k,
      version_activa_consentimiento: req.body?.version_activa_consentimiento,
      correlacionId: req.correlacionId,
    })
  );
});
