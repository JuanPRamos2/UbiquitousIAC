/**
 * Manejo y mapeo centralizado de errores de PostgreSQL para catalog-service.
 * Mapeo según requisitos de diseño:
 *   - 23505 (unique_violation) -> 409 Conflicto
 *   - 23503 (foreign_key_violation) -> 422 Entidad no procesable (o 409)
 *   - 23514 (check_violation) -> 422 Entidad no procesable
 */

export class HttpError extends Error {
  constructor(status, code, message, extra = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.extra = extra;
  }
}

export function mapearErrorPg(err) {
  if (!err) return err;

  // 23505: unique_violation
  if (err.code === "23505") {
    return new HttpError(
      409,
      "CONFLICTO_DUPLICADO",
      `Registro duplicado: ${err.detail || "Ya existe un registro con esos datos únicos"}`,
      {
        codigo_pg: err.code,
        constraint: err.constraint,
        detalle: err.detail,
      }
    );
  }

  // 23503: foreign_key_violation
  if (err.code === "23503") {
    return new HttpError(
      422,
      "ERROR_REFERENCIA",
      `Referencia inválida: ${err.detail || "La entidad referenciada no existe o tiene dependencias"}`,
      {
        codigo_pg: err.code,
        constraint: err.constraint,
        detalle: err.detail,
      }
    );
  }

  // 23514: check_violation
  if (err.code === "23514") {
    return new HttpError(
      422,
      "REGLA_INTEGRIDAD",
      `Violación de regla CHECK: ${err.constraint || "Los datos no cumplen las restricciones del catálogo"}`,
      {
        codigo_pg: err.code,
        constraint: err.constraint,
      }
    );
  }

  return err;
}

export function asyncHandler(fn) {
  return (req, res, next) => {
    Promise.resolve(fn(req, res, next)).catch((err) => next(mapearErrorPg(err)));
  };
}
