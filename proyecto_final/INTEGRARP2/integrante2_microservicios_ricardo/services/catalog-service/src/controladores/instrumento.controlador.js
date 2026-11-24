import * as servicio from "../servicios/instrumento.servicio.js";
import { asyncHandler } from "../utilidades/pg-errores.js";
import { responderCatalogo } from "../utilidades/serializador.js";

export const listar = asyncHandler(async (req, res) => {
  const resultado = await servicio.listarInstrumentos(req.query);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

export const obtenerPorId = asyncHandler(async (req, res) => {
  const resultado = await servicio.obtenerInstrumentoPorId(req.params.id);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

export const crear = asyncHandler(async (req, res) => {
  const resultado = await servicio.crearInstrumento(req.body);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 201 });
});

export const actualizar = asyncHandler(async (req, res) => {
  const resultado = await servicio.actualizarInstrumento(req.params.id, req.body);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

export const eliminarLogico = asyncHandler(async (req, res) => {
  const resultado = await servicio.eliminarInstrumentoLogico(req.params.id);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

// Versiones
export const listarVersiones = asyncHandler(async (req, res) => {
  const resultado = await servicio.listarVersiones(req.params.id, req.query);
  responderCatalogo(req, res, { data: resultado }, { rootTag: "catalogo", status: 200 });
});

export const obtenerVersion = asyncHandler(async (req, res) => {
  const resultado = await servicio.obtenerVersion(req.params.id, req.params.version);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

export const crearVersion = asyncHandler(async (req, res) => {
  const resultado = await servicio.crearVersion(req.params.id, req.body);
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 201 });
});

export const actualizarVersion = asyncHandler(async (req, res) => {
  const resultado = await servicio.actualizarVersion(
    req.params.id,
    req.params.version,
    req.body
  );
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});

export const eliminarVersionLogico = asyncHandler(async (req, res) => {
  const resultado = await servicio.eliminarVersionLogica(
    req.params.id,
    req.params.version
  );
  responderCatalogo(req, res, resultado, { rootTag: "catalogo", status: 200 });
});
