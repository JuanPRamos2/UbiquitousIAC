import * as servicio from "../servicios/campania.servicio.js";
import { asyncHandler } from "../utilidades/pg-errores.js";
import { responderCatalogo } from "../utilidades/serializador.js";

export const listar = asyncHandler(async (req, res) => {
  const resultado = await servicio.listarCampanias(req.actor, req.query);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

export const obtenerPorId = asyncHandler(async (req, res) => {
  const resultado = await servicio.obtenerCampaniaPorId(req.params.id);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

export const crear = asyncHandler(async (req, res) => {
  const resultado = await servicio.crearCampania(req.body);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 201 });
});

export const actualizar = asyncHandler(async (req, res) => {
  const resultado = await servicio.actualizarCampania(req.params.id, req.body);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

export const eliminarLogico = asyncHandler(async (req, res) => {
  const resultado = await servicio.eliminarCampaniaLogica(req.params.id);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});
