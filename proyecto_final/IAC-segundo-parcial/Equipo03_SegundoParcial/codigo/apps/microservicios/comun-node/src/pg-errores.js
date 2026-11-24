/**
 * Traduccion de codigos de error SQL de PostgreSQL a excepciones ErrorApi.
 *
 * Mapeo estandarizado:
 *   23505 (unique_violation)        -> 409 RECURSO_DUPLICADO
 *   23503 (foreign_key_violation)   -> 422 REFERENCIA_INVALIDA
 *   23514 (check_violation)         -> 422 RESTRICCION_VIOLADA
 *   42501 (insufficient_privilege)  -> 403 PERMISO_DENEGADO
 */
import { ErrorApi } from "./errores.js";

export function traducirErrorPg(err, mensajePorDefecto = "Error en base de datos relacional") {
  if (!err) return err;

  const codigo = String(err.code || "");
  const detalle = err.detail || err.message || "";

  if (codigo === "23505") {
    return new ErrorApi(
      "RECURSO_DUPLICADO",
      "Ya existe un registro con la misma clave o identificador unico.",
      409,
      [{ codigo_pg: "23505", detalle }]
    );
  }

  if (codigo === "23503") {
    return new ErrorApi(
      "REFERENCIA_INVALIDA",
      "La operacion hace referencia a un registro inexistente o depende de entidades vinculadas.",
      422,
      [{ codigo_pg: "23503", detalle }]
    );
  }

  if (codigo === "23514") {
    return new ErrorApi(
      "RESTRICCION_VIOLADA",
      "Los datos proporcionados no cumplen las reglas de integridad de la base de datos.",
      422,
      [{ codigo_pg: "23514", detalle }]
    );
  }

  if (codigo === "42501") {
    return new ErrorApi(
      "PERMISO_DENEGADO",
      "No se tienen privilegios suficientes para ejecutar la consulta SQL solicitada.",
      403,
      [{ codigo_pg: "42501", detalle }]
    );
  }

  return new ErrorApi("ERROR_BASE_DATOS", mensajePorDefecto, 500, [
    { codigo_pg: codigo, detalle: String(err.message || "") },
  ]);
}
