import * as db from "../modelos/catalogo.db.js";
import * as servicio from "../servicios/instrumento.servicio.js";
import { asyncHandler } from "../utilidades/pg-errores.js";
import { responderCatalogo, responderLista,
         responderUno } from "../utilidades/serializador.js";

export const listar = asyncHandler(async (req, res) => {
  const resultado = await servicio.listarInstrumentos(req.query);
  responderLista(req, res, "instrumentos", resultado);
});

export const obtenerPorId = asyncHandler(async (req, res) => {
  const resultado = await servicio.obtenerInstrumentoPorId(req.params.id);
  responderUno(req, res, "instrumento", resultado);
});

export const crear = asyncHandler(async (req, res) => {
  const resultado = await servicio.crearInstrumento(req.body);
  responderUno(req, res, "instrumento", resultado, { status: 201 });
});

export const actualizar = asyncHandler(async (req, res) => {
  const resultado = await servicio.actualizarInstrumento(req.params.id, req.body);
  responderUno(req, res, "instrumento", resultado);
});

export const eliminarLogico = asyncHandler(async (req, res) => {
  const resultado = await servicio.eliminarInstrumentoLogico(req.params.id);
  responderUno(req, res, "instrumento", resultado);
});

// ------------------------------------------------------------- versiones
// La escala (escala_min, escala_max) vive en la version y no en el
// reactivo: el mismo reactivo puede medirse 1-5 en una version y 1-7 en la
// siguiente, y los agregados de campanias viejas tienen que seguir
// interpretandose con la escala que estaba vigente cuando se respondieron.

export const listarVersiones = asyncHandler(async (req, res) => {
  const resultado = await servicio.listarVersiones(req.params.id, req.query);
  const filas = resultado.rows || resultado;
  responderLista(req, res, "versiones",
    { rows: filas, total: resultado.total ?? filas.length,
      page: resultado.page ?? 1, limit: resultado.limit ?? (filas.length || 1),
      totalPages: resultado.totalPages });
});

export const obtenerVersion = asyncHandler(async (req, res) => {
  const resultado = await servicio.obtenerVersion(req.params.id, req.params.version);
  responderUno(req, res, "version", resultado);
});

export const crearVersion = asyncHandler(async (req, res) => {
  const resultado = await servicio.crearVersion(req.params.id, req.body);
  responderUno(req, res, "version", resultado, { status: 201 });
});

export const actualizarVersion = asyncHandler(async (req, res) => {
  const resultado = await servicio.actualizarVersion(
    req.params.id, req.params.version, req.body);
  responderUno(req, res, "version", resultado);
});

export const eliminarVersionLogico = asyncHandler(async (req, res) => {
  const resultado = await servicio.eliminarVersionLogica(
    req.params.id, req.params.version);
  responderUno(req, res, "version", resultado);
});

// ---------------------------------------------------------------------------
// Catalogos de apoyo. Son de solo lectura a proposito: las dimensiones las
// define la metodologia del instrumento y las fuentes autorizadas son una
// decision de gobernanza, no de operacion. catalogo.fuente_autorizada
// incluye filas con autorizada = FALSE (correo, chat, GPS, teclado,
// navegacion) que estan ahi para dejar por escrito lo que el sistema NO
// puede medir; un endpoint de escritura permitiria autorizarlas.
// ---------------------------------------------------------------------------

export const listarDimensiones = asyncHandler(async (req, res) => {
  const dimensiones = await db.dbListarDimensiones();
  responderCatalogo(req, res, { dimensiones, total: dimensiones.length },
                    { rootTag: "dimensiones_respuesta" });
});

export const listarFuentes = asyncHandler(async (req, res) => {
  const fuentes = await db.dbListarFuentes();
  responderCatalogo(req, res, { fuentes, total: fuentes.length },
                    { rootTag: "fuentes_respuesta" });
});

export const listarParametros = asyncHandler(async (req, res) => {
  const parametros = await db.dbListarParametros();
  responderCatalogo(req, res, { parametros, total: parametros.length },
                    { rootTag: "parametros_respuesta" });
});
