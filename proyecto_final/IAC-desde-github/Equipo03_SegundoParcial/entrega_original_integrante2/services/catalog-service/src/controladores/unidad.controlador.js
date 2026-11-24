import * as servicio from "../servicios/unidad.servicio.js";
import { asyncHandler } from "../utilidades/pg-errores.js";
import { responderCatalogo } from "../utilidades/serializador.js";

export const listar = asyncHandler(async (req, res) => {
  const resultado = await servicio.listarUnidades(req.actor, req.query);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

export const obtenerPorId = asyncHandler(async (req, res) => {
  const resultado = await servicio.obtenerUnidadPorId(req.params.id);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

export const crear = asyncHandler(async (req, res) => {
  const resultado = await servicio.crearUnidad(req.body);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 201 });
});

export const actualizar = asyncHandler(async (req, res) => {
  const resultado = await servicio.actualizarUnidad(req.params.id, req.body);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

export const eliminarLogico = asyncHandler(async (req, res) => {
  const resultado = await servicio.eliminarUnidadLogica(req.params.id);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});
