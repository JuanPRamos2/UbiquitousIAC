import * as Portal from "../servicios/portal.servicio.js";
import { asyncHandler } from "../utilidades/errores.js";

export const escritorio = asyncHandler(async (req, res) => {
  try {
    res.json(await Portal.escritorio(req.actor));
  } catch (err) {
    console.error("portal.escritorio", err.message);
    res.json({
      perfil: req.actor?.perfil,
      unidad_organizacional_id: null,
      unidades: [],
      campanias: [],
      instrumentos: [],
      k: 5,
      parametros: {},
    });
  }
});

export const miConsentimiento = asyncHandler(async (req, res) => {
  res.json(await Portal.miConsentimiento(req.actor));
});

export const cambiarConsentimiento = asyncHandler(async (req, res) => {
  res.json(
    await Portal.cambiarMiConsentimiento({
      actor: req.actor,
      aceptar: Boolean(req.body?.aceptar),
      correlacionId: req.correlacionId,
    })
  );
});

export const misEvaluaciones = asyncHandler(async (req, res) => {
  res.json(await Portal.misEvaluaciones(req.actor));
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

export const listarSoporte = asyncHandler(async (req, res) => {
  res.json(await Portal.listarApoyo());
});

export const cuentas = asyncHandler(async (req, res) => {
  res.json(await Portal.cuentas());
});

export const configuracion = asyncHandler(async (req, res) => {
  res.json(await Portal.configuracion());
});

export const guardarConfiguracion = asyncHandler(async (req, res) => {
  res.json(
    await Portal.guardarConfiguracion({
      actor: req.actor,
      k: req.body?.k,
      version_activa_consentimiento: req.body?.version_activa_consentimiento,
      correlacionId: req.correlacionId,
    })
  );
});
