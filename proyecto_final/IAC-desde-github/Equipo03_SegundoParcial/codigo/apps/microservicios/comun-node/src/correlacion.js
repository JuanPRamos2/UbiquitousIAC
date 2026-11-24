/**
 * Identificador de correlacion por peticion.
 *
 * Si el cliente ya trae uno se respeta: asi una operacion que pasa por el
 * sistema web, auth-service y main-process-service se puede seguir
 * completa en la bitacora con un solo identificador.
 */
import { randomUUID } from "node:crypto";

export function correlacion(req, res, next) {
  req.correlacionId = req.headers["x-correlacion-id"] || randomUUID().replace(/-/g, "").slice(0, 16);
  res.setHeader("X-Correlacion-Id", req.correlacionId);
  next();
}
