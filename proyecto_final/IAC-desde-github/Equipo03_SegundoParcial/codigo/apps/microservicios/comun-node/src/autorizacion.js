/**
 * Autorizacion por permiso, consultada en la base en CADA peticion.
 *
 * Los permisos no viajan en el token a proposito: si viajaran, quitarle un
 * permiso a un perfil no surtiria efecto hasta que caducaran todos los
 * tokens ya emitidos. El modelo es el mismo del primer parcial
 * (usuarios.permiso y usuarios.perfil_permiso), de modo que el sistema web
 * y los ocho microservicios autorizan con la misma tabla.
 */
import { ErrorApi } from "./errores.js";
import { consultar } from "./postgres.js";

export async function permisosDe(perfilId) {
  const filas = await consultar(
    `SELECT p.codigo
       FROM usuarios.perfil_permiso pp
       JOIN usuarios.permiso p USING (permiso_id)
      WHERE pp.perfil_id = $1`,
    [perfilId]
  );
  return new Set(filas.map((f) => f.codigo));
}

/** Middleware: exige al menos uno de los permisos indicados. */
export function autorizar(...codigos) {
  return async function (req, res, next) {
    try {
      if (!req.actor) {
        throw new ErrorApi("TOKEN_AUSENTE", "La ruta exige autenticacion.", 401);
      }
      const permisos = await permisosDe(req.actor.perfil_id);
      req.permisos = permisos;
      if (!codigos.some((c) => permisos.has(c))) {
        throw new ErrorApi("SIN_PERMISO",
          `El perfil ${req.actor.perfil || ""} no tiene ninguno de los ` +
          `permisos requeridos: ${codigos.join(", ")}.`, 403);
      }
      next();
    } catch (e) {
      next(e);
    }
  };
}

/** Alias con el nombre que usan los servicios en Python. */
export const requierePermiso = autorizar;
