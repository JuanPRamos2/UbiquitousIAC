import { HttpError } from "../utilidades/errores.js";

export function manejadorErrores(err, _req, res, _next) {
  if (err instanceof HttpError) {
    return res.status(err.status).json({
      error: err.code,
      mensaje: err.message,
      ...err.extra,
    });
  }
  console.error(err);
  return res.status(500).json({
    error: "ERROR_TECNICO",
    mensaje: "Error interno",
  });
}
