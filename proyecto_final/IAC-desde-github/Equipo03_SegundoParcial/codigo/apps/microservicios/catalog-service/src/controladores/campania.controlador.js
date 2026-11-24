import * as servicio from "../servicios/campania.servicio.js";
import { asyncHandler } from "../utilidades/pg-errores.js";
import { responderLista, responderUno } from "../utilidades/serializador.js";

export const listar = asyncHandler(async (req, res) => {
  const resultado = await servicio.listarCampanias(req.actor, req.query);
  responderLista(req, res, "campanias", resultado);
});

export const obtenerPorId = asyncHandler(async (req, res) => {
  const resultado = await servicio.obtenerCampaniaPorId(req.params.id);
  // El padron (que unidades estan convocadas) viaja junto con la campania
  // cuando el servicio lo resuelve: la unidad de una respuesta se toma de
  // ahi y nunca de lo que mande el cliente.
  const { unidades, ...campania } = resultado || {};
  responderUno(req, res, "campania", campania,
               unidades ? { extra: { unidades } } : {});
});

export const crear = asyncHandler(async (req, res) => {
  const resultado = await servicio.crearCampania(req.body);
  responderUno(req, res, "campania", resultado, { status: 201 });
});

export const actualizar = asyncHandler(async (req, res) => {
  const resultado = await servicio.actualizarCampania(req.params.id, req.body);
  responderUno(req, res, "campania", resultado);
});

export const eliminarLogico = asyncHandler(async (req, res) => {
  const resultado = await servicio.eliminarCampaniaLogica(req.params.id);
  responderUno(req, res, "campania", resultado);
});
