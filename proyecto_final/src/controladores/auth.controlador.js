import * as Auth from "../servicios/auth.servicio.js";
import { asyncHandler } from "../utilidades/errores.js";

export const login = asyncHandler(async (req, res) => {
  const { correo, contrasena } = req.body || {};
  if (!correo || !contrasena) {
    return res.status(400).json({ error: "PAYLOAD_INVALIDO", mensaje: "correo y contrasena son obligatorios" });
  }
  const out = await Auth.login({
    correo,
    contrasena,
    correlacionId: req.correlacionId,
  });
  res.json(out);
});

export const logout = asyncHandler(async (req, res) => {
  await Auth.logout({
    jti: req.actor.jti,
    exp: req.actor.exp,
    actor: req.actor,
    correlacionId: req.correlacionId,
  });
  res.json({ ok: true });
});

export const me = asyncHandler(async (req, res) => {
  res.json(await Auth.sesionActual(req.actor));
});
