import * as Catalogos from "../servicios/catalogo.servicio.js";
import { asyncHandler } from "../utilidades/errores.js";

export const unidades = asyncHandler(async (req, res) => {
  res.json({ data: await Catalogos.unidades(req.actor) });
});

export const campanias = asyncHandler(async (req, res) => {
  res.json({ data: await Catalogos.campanias(req.actor) });
});

export const reactivos = asyncHandler(async (req, res) => {
  const { instrumento_id, version } = req.params;
  res.json({
    data: await Catalogos.reactivos(instrumento_id, Number(version)),
  });
});

export const instrumentos = asyncHandler(async (_req, res) => {
  res.json({ data: await Catalogos.instrumentos() });
});

export const versionesConsentimiento = asyncHandler(async (_req, res) => {
  res.json({ data: await Catalogos.versionesConsentimiento() });
});

export const cuentas = asyncHandler(async (_req, res) => {
  res.json(await Catalogos.cuentas());
});
