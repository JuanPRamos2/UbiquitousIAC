/**
 * Alcance de un lider sobre el arbol real: organizacion.unidad_organizacional.
 *
 * La columna es unidad_organizacional_id y el padre es unidad_padre_id.
 * El token trae unidad_alcance (null si el perfil ve toda la organizacion).
 */
import { ErrorApi } from "./errores.js";
import { consultar } from "./postgres.js";

export async function obtenerUnidadesSubordinadas(unidadRaizId) {
  if (!unidadRaizId) return [];
  const filas = await consultar(
    `WITH RECURSIVE jerarquia AS (
       SELECT unidad_organizacional_id
         FROM organizacion.unidad_organizacional
        WHERE unidad_organizacional_id = $1 AND activa = true
       UNION ALL
       SELECT u.unidad_organizacional_id
         FROM organizacion.unidad_organizacional u
         JOIN jerarquia j ON u.unidad_padre_id = j.unidad_organizacional_id
        WHERE u.activa = true
     )
     SELECT unidad_organizacional_id FROM jerarquia`,
    [unidadRaizId]
  );
  return filas.map((f) => f.unidad_organizacional_id);
}

export async function validarAlcanceUnidad(actor, unidadDestinoId) {
  if (!actor) {
    throw new ErrorApi("TOKEN_AUSENTE", "Se requiere identidad de actor para verificar alcance.", 401);
  }

  const unidadActor = actor.unidad_alcance || actor.unidad_id || actor.unidad || null;
  // Sin unidad de alcance el perfil ve toda la organizacion
  // (administrador, especialista, auditor).
  if (!unidadActor) return true;
  if (unidadDestinoId === unidadActor) return true;

  const permitidas = await obtenerUnidadesSubordinadas(unidadActor);
  if (!permitidas.includes(unidadDestinoId)) {
    throw new ErrorApi(
      "FUERA_DE_ALCANCE",
      "Solo puedes consultar tu unidad y las que dependen de ella.",
      403,
      [{ unidad_solicitada: unidadDestinoId, unidad_actor: unidadActor }]
    );
  }
  return true;
}
