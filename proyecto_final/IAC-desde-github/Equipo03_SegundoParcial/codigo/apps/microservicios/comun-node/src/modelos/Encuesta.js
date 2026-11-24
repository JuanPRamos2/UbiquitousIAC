/**
 * Documento de la respuesta de encuesta, en MongoDB.
 *
 * Reparto deliberado entre las dos bases:
 *
 *   PostgreSQL es la autoridad. Los valores numericos que alimentan la
 *   agregacion protegida se escriben con
 *   autoreporte.fn_registrar_autoreporte, que hace cumplir RN-01 (una
 *   respuesta por campania), RN-02 (consentimiento vigente) y el rango de
 *   la escala. Ningun servicio escribe esas tablas por su cuenta.
 *
 *   MongoDB guarda el DOCUMENTO de la entrega: la carga tal como llego,
 *   con sus comentarios en texto libre y los metadatos que cambian de un
 *   instrumento a otro. Modelar eso en columnas obligaria a una tabla con
 *   decenas de columnas nulas o a un antipatron entidad-atributo-valor.
 *
 * El indice unico (seudonimo_id, campania_id) deja la regla "una por
 * campania" tambien escrita en esta base, de modo que no dependa de que
 * el servicio la recuerde.
 */
import { base, verificarSinIdentidad } from "../mongo.js";
import { tuberiaRespuestasPorUnidadCampania } from "./pipelinesMongo.js";

export const COLECCION = "respuestas_encuesta";

function coleccion(col) {
  return col || base().collection(COLECCION);
}

export async function guardarDocumentoRespuesta(doc, col) {
  const documento = {
    seudonimo_id: doc.seudonimo_id,
    campania_id: doc.campania_id,
    unidad_organizacional_id: doc.unidad_organizacional_id || null,
    instrumento_id: doc.instrumento_id || null,
    version_instrumento: doc.version_instrumento ?? null,
    valores: doc.valores || {},
    comentario: doc.comentario ?? null,
    metadatos: doc.metadatos || {},
    correlacion_id: doc.correlacion_id || "",
    fecha: doc.fecha ? new Date(doc.fecha) : new Date(),
  };
  verificarSinIdentidad(documento);
  const r = await coleccion(col).insertOne(documento);
  return { ...documento, _id: r.insertedId, id: String(r.insertedId) };
}

export async function buscarPorSeudonimo(seudonimo_id, col) {
  return coleccion(col)
    .find({ seudonimo_id }, { projection: { _id: 0 } })
    .sort({ fecha: -1 })
    .toArray();
}

export async function buscarPorSeudonimoCampania(seudonimo_id, campania_id, col) {
  return coleccion(col).findOne({ seudonimo_id, campania_id }, { projection: { _id: 0 } });
}

/** Agregacion: respuestas por unidad y campania. */
export async function agregarRespuestasPorUnidadCampania(filtros = {}, col) {
  const tuberia = tuberiaRespuestasPorUnidadCampania(filtros);
  return coleccion(col).aggregate(tuberia).toArray();
}

export async function actualizarComentario(seudonimo_id, campania_id, comentario, col) {
  const r = await coleccion(col).findOneAndUpdate(
    { seudonimo_id, campania_id },
    { $set: { comentario: comentario ?? null, fecha_actualizacion: new Date() } },
    { returnDocument: "after", projection: { _id: 0 } }
  );
  return r?.value ?? r ?? null;
}
