import * as Encuesta from "../servicios/encuesta.servicio.js";
import * as Consentimiento from "../servicios/consentimiento.servicio.js";
import * as Portal from "../servicios/portal.servicio.js";
import { asyncHandler } from "../utilidades/errores.js";

export const crear = asyncHandler(async (req, res) => {
  const out = await Encuesta.guardarAutoreporte({
    actor: req.actor,
    body: req.body,
    correlacionId: req.correlacionId,
  });
  res.status(201).json(out);
});

export const estado = asyncHandler(async (req, res) => {
  res.json(
    await Encuesta.estadoRespuesta({
      actor: req.actor,
      campaniaId: req.query.campania_id,
    })
  );
});

export const miConsentimiento = asyncHandler(async (req, res) => {
  res.json(await Consentimiento.mio(req.actor));
});

export const cambiarConsentimiento = asyncHandler(async (req, res) => {
  res.json(
    await Consentimiento.cambiarMio({
      actor: req.actor,
      aceptar: Boolean(req.body?.aceptar),
      correlacionId: req.correlacionId,
    })
  );
});

export const mias = asyncHandler(async (req, res) => {
  res.json(await Encuesta.mias(req.actor));
});

export const misAccesos = asyncHandler(async (req, res) => {
  res.json(await Encuesta.misAccesos(req.actor));
});

export const crearSoporte = asyncHandler(async (req, res) => {
  res.status(201).json(
    await Portal.solicitarApoyo({
      actor: req.actor,
      mensaje: req.body?.mensaje,
      correlacionId: req.correlacionId,
    })
  );
});
