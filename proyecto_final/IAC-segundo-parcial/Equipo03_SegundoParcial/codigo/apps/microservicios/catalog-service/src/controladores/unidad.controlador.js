import * as servicio from "../servicios/unidad.servicio.js";
import { asyncHandler } from "../utilidades/pg-errores.js";
import { responderLista, responderUno } from "../utilidades/serializador.js";

export const listar = asyncHandler(async (req, res) => {
  const resultado = await servicio.listarUnidades(req.actor, req.query);
  responderLista(req, res, "unidades", resultado);
});

export const obtenerPorId = asyncHandler(async (req, res) => {
  const resultado = await servicio.obtenerUnidadPorId(req.params.id);
  responderUno(req, res, "unidad", resultado);
});

export const crear = asyncHandler(async (req, res) => {
  const resultado = await servicio.crearUnidad(req.body);
  responderUno(req, res, "unidad", resultado, { status: 201 });
});

export const actualizar = asyncHandler(async (req, res) => {
  const resultado = await servicio.actualizarUnidad(req.params.id, req.body);
  responderUno(req, res, "unidad", resultado);
});

// Baja LOGICA: la unidad se marca inactiva y sigue ahi. Un DELETE real
// romperia las llaves foraneas de las respuestas ya registradas, o dejaria
// huerfanos los agregados de campanias pasadas.
export const eliminarLogico = asyncHandler(async (req, res) => {
  const resultado = await servicio.eliminarUnidadLogica(req.params.id);
  responderUno(req, res, "unidad", resultado);
});
