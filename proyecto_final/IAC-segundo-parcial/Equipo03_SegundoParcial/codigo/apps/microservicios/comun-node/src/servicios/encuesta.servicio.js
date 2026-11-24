/**
 * Registro de una respuesta de encuesta: el proceso principal del negocio.
 *
 * Escribe en las DOS bases, con una division que no es arbitraria:
 *
 *   1. PostgreSQL, por medio de autoreporte.fn_registrar_autoreporte.
 *      Esa funcion es propiedad del rol motor, corre con SECURITY DEFINER
 *      y hace cumplir por dentro RN-01 (una respuesta por campania),
 *      RN-02 (consentimiento vigente), la campania abierta, la
 *      completitud del instrumento y el rango de la escala. El rol de la
 *      aplicacion NO tiene permiso sobre el esquema autoreporte: esta es
 *      la unica via de escritura, y por eso las reglas siguen valiendo
 *      aunque el cliente sea este microservicio y no el sistema web.
 *
 *   2. MongoDB, con el documento de la entrega: los valores tal como
 *      llegaron, el comentario en texto libre y los metadatos del envio,
 *      que cambian de un instrumento a otro.
 *
 * El orden importa. Primero PostgreSQL: si la respuesta no es valida, no
 * se escribe nada en ninguna de las dos bases. Si PostgreSQL acepta y
 * MongoDB falla, la respuesta numerica ya quedo registrada y el documento
 * se reporta como pendiente en lugar de perder la respuesta de la
 * persona, que no la va a volver a contestar.
 */
import { ErrorApi } from "../errores.js";
import { consultarUno } from "../postgres.js";
import * as Encuesta from "../modelos/Encuesta.js";
import { contextoOperativo } from "../modelos/Usuario.js";

/** Traduccion de los estados que devuelve la funcion a codigos HTTP. */
const ESTADOS = {
  REGISTRADA: { http: 201, codigo: null },
  CAMPANIA_NO_ABIERTA: { http: 409, codigo: "CAMPANIA_NO_ABIERTA" },
  SIN_CONSENTIMIENTO: { http: 403, codigo: "SIN_CONSENTIMIENTO" },
  YA_RESPONDIDA: { http: 409, codigo: "YA_RESPONDIDA" },
  SEUDONIMO_INVALIDO: { http: 403, codigo: "SEUDONIMO_INVALIDO" },
  RESPUESTA_INCOMPLETA: { http: 422, codigo: "RESPUESTA_INCOMPLETA" },
};

export async function guardarAutoreporte({ actor, cuerpo, correlacionId, colRespuestas }) {
  const campaniaId = String(cuerpo?.campania_id || "").trim();
  const valores = cuerpo?.valores;

  if (!campaniaId) {
    throw new ErrorApi("PARAMETRO_FALTANTE", "Falta 'campania_id'.", 400);
  }
  if (!valores || typeof valores !== "object" || Array.isArray(valores)) {
    throw new ErrorApi("PARAMETRO_INVALIDO",
      "'valores' debe ser un objeto { reactivo_id: valor }.", 400);
  }
  for (const [reactivo, v] of Object.entries(valores)) {
    if (!Number.isInteger(v)) {
      throw new ErrorApi("PARAMETRO_INVALIDO",
        `El valor del reactivo ${reactivo} debe ser un entero.`, 400,
        [{ campo: `valores.${reactivo}`, problema: "no es entero" }]);
    }
  }

  // El seudonimo se resuelve en la base en cada peticion y no se acepta
  // del cliente: aceptarlo permitiria responder en nombre de otra persona.
  const ctx = await contextoOperativo(actor?.sub || actor?.usuario_id);
  if (!ctx?.seudonimo_id) {
    throw new ErrorApi("SIN_SEUDONIMO",
      "La cuenta no tiene participacion operativa en el programa.", 403);
  }

  const fila = await consultarUno(
    "SELECT estado, mensaje FROM autoreporte.fn_registrar_autoreporte($1, $2, $3::jsonb)",
    [ctx.seudonimo_id, campaniaId, JSON.stringify(valores)]
  );
  const resultado = ESTADOS[fila?.estado] || { http: 422, codigo: "RECHAZADA" };
  if (resultado.codigo) {
    throw new ErrorApi(resultado.codigo, fila.mensaje, resultado.http);
  }

  const campania = await consultarUno(
    `SELECT campania_id, instrumento_id, version_instrumento
       FROM catalogo.campania WHERE campania_id = $1`,
    [campaniaId]
  );

  let documento = null;
  let documentoPendiente = false;
  try {
    documento = await Encuesta.guardarDocumentoRespuesta({
      seudonimo_id: ctx.seudonimo_id,
      campania_id: campaniaId,
      unidad_organizacional_id: ctx.unidad_organizacional_id,
      instrumento_id: campania?.instrumento_id || null,
      version_instrumento: campania?.version_instrumento ?? null,
      valores,
      comentario: cuerpo?.comentario ? String(cuerpo.comentario).slice(0, 2000) : null,
      metadatos: { origen: "main-process-service" },
      correlacion_id: correlacionId,
    }, colRespuestas);
  } catch (e) {
    if (e instanceof ErrorApi && e.codigo === "CAMPO_PROHIBIDO") throw e;
    documentoPendiente = true;
  }

  return {
    estado: "REGISTRADA",
    mensaje: fila.mensaje,
    seudonimo_id: ctx.seudonimo_id,
    campania_id: campaniaId,
    instrumento_id: campania?.instrumento_id || null,
    version_instrumento: campania?.version_instrumento ?? null,
    documento_id: documento?.id || null,
    documento_pendiente: documentoPendiente,
  };
}
