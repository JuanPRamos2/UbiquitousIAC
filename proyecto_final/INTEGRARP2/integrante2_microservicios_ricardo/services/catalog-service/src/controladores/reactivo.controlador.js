import * as servicio from "../servicios/reactivo.servicio.js";
import { asyncHandler } from "../utilidades/pg-errores.js";
import { responderCatalogo } from "../utilidades/serializador.js";

export const listar = asyncHandler(async (req, res) => {
  const resultado = await servicio.listarReactivos(req.query);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

export const obtenerPorId = asyncHandler(async (req, res) => {
  const resultado = await servicio.obtenerReactivoPorId(req.params.id);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

export const crear = asyncHandler(async (req, res) => {
  const resultado = await servicio.crearReactivo(req.body);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 201 });
});

export const actualizar = asyncHandler(async (req, res) => {
  const resultado = await servicio.actualizarReactivo(req.params.id, req.body);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

export const eliminarLogico = asyncHandler(async (req, res) => {
  const resultado = await servicio.eliminarReactivoLogico(req.params.id);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

// Reactivos asociados a versión
export const reactivosDeVersion = asyncHandler(async (req, res) => {
  const { instrumento_id, version } = req.params;
  const resultado = await servicio.reactivosDeVersion(instrumento_id, Number(version));
  responderCatalogo(req, res, { data: resultado }, { rootTag: "catalogo", status: 200 });
});

export const asociarAVersion = asyncHandler(async (req, res) => {
  const { instrumento_id, version } = req.params;
  const resultado = await servicio.asociarAVersion(instrumento_id, Number(version), req.body);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 201 });
});

export const desasociarDeVersion = asyncHandler(async (req, res) => {
  const { instrumento_id, version, reactivo_id } = req.params;
  const resultado = await servicio.desasociarDeVersion(instrumento_id, Number(version), reactivo_id);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});
