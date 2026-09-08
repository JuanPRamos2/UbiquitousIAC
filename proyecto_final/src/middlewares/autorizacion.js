import { HttpError } from "../utilidades/errores.js";

export function autorizar(...perfiles) {
  return (req, _res, next) => {
    if (!req.actor) return next(new HttpError(401, "SIN_SESION", "No autenticado"));
    if (!perfiles.includes(req.actor.perfil)) {
      return next(new HttpError(403, "RBAC", "Perfil sin permiso para este recurso"));
    }
    next();
  };
}
