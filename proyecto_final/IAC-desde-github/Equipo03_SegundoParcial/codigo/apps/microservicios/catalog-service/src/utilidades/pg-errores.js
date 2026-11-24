/**
 * Mapeo de errores de PostgreSQL a codigos HTTP.
 *
 * Sin esta capa, una violacion de unicidad al crear una unidad llegaria al
 * cliente como 500 "Error interno", que es informacion falsa: el servicio
 * funciono bien y fue la peticion la que pidio algo imposible. El codigo
 * correcto es 409 y el cliente puede actuar en consecuencia.
 *
 *   23505 unique_violation      -> 409 CONFLICTO_DUPLICADO
 *   23503 foreign_key_violation -> 422 ERROR_REFERENCIA
 *   23514 check_violation       -> 422 REGLA_INTEGRIDAD
 *   23502 not_null_violation    -> 422 CAMPO_REQUERIDO
 *   42501 insufficient_privilege-> 403 PRIVILEGIO_INSUFICIENTE
 */
import { ErrorApi, HttpError } from "@bienestar/comun/errores.js";

export { HttpError };

export function mapearErrorPg(err) {
  if (!err) return err;
  if (err instanceof ErrorApi) return err;

  const base = { codigo_pg: err.code, constraint: err.constraint, detalle: err.detail };

  if (err.code === "23505") {
    return new HttpError(409, "CONFLICTO_DUPLICADO",
      `Registro duplicado: ${err.detail || "ya existe un registro con esos datos unicos"}`,
      base);
  }
  if (err.code === "23503") {
    return new HttpError(422, "ERROR_REFERENCIA",
      `Referencia invalida: ${err.detail || "la entidad referenciada no existe o tiene dependencias"}`,
      base);
  }
  if (err.code === "23514") {
    return new HttpError(422, "REGLA_INTEGRIDAD",
      `No se cumple la restriccion ${err.constraint || "del catalogo"}.`, base);
  }
  if (err.code === "23502") {
    return new HttpError(422, "CAMPO_REQUERIDO",
      `Falta el campo obligatorio ${err.column || ""}.`.trim(), base);
  }
  // El rol de la aplicacion tiene privilegio minimo a proposito. Si una
  // consulta nueva toca algo que no le corresponde, el 403 lo dice con
  // claridad en lugar de esconderlo en un 500.
  if (err.code === "42501") {
    return new HttpError(403, "PRIVILEGIO_INSUFICIENTE",
      "El rol de la aplicacion no tiene permiso para esta operacion.", base);
  }
  return err;
}

export function asyncHandler(fn) {
  return (req, res, next) => {
    Promise.resolve(fn(req, res, next)).catch((err) => next(mapearErrorPg(err)));
  };
}
