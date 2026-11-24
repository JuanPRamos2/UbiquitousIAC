import * as servicio from "../servicios/reactivo.servicio.js";
import { asyncHandler } from "../utilidades/pg-errores.js";
import { responderLista, responderUno } from "../utilidades/serializador.js";

export const listar = asyncHandler(async (req, res) => {
  const resultado = await servicio.listarReactivos(req.query);
  responderLista(req, res, "reactivos", resultado);
});

export const obtenerPorId = asyncHandler(async (req, res) => {
  const resultado = await servicio.obtenerReactivoPorId(req.params.id);
  responderUno(req, res, "reactivo", resultado);
});

export const crear = asyncHandler(async (req, res) => {
  const resultado = await servicio.crearReactivo(req.body);
  responderUno(req, res, "reactivo", resultado, { status: 201 });
});

export const actualizar = asyncHandler(async (req, res) => {
  const resultado = await servicio.actualizarReactivo(req.params.id, req.body);
  responderUno(req, res, "reactivo", resultado);
});

export const eliminarLogico = asyncHandler(async (req, res) => {
  const resultado = await servicio.eliminarReactivoLogico(req.params.id);
  responderUno(req, res, "reactivo", resultado);
});

// ------------------------------- reactivos asociados a una version
// La asociacion vive en catalogo.reactivo_version. Aqui si se admite
// desasociar: quitar un reactivo de una version no borra el reactivo ni
// ninguna respuesta ya registrada.

export const reactivosDeVersion = asyncHandler(async (req, res) => {
  const { instrumento_id, version } = req.params;
  const filas = await servicio.reactivosDeVersion(instrumento_id, Number(version));
  // Raiz propia: un reactivo visto DENTRO de una version trae orden,
  // obligatoriedad y escala, que no estan en el reactivo suelto. Es otra
  // forma y por eso es otro elemento raiz, con su tipo en catalogos.xsd.
  responderLista(req, res, "reactivos",
    { rows: filas, total: filas.length, page: 1, limit: filas.length || 1 },
    { raiz: "reactivos_version_respuesta" });
});

export const asociarAVersion = asyncHandler(async (req, res) => {
  const { instrumento_id, version } = req.params;
  const resultado = await servicio.asociarAVersion(instrumento_id, Number(version), req.body);
  responderUno(req, res, "reactivo", resultado, { status: 201 });
});

export const desasociarDeVersion = asyncHandler(async (req, res) => {
  const { instrumento_id, version, reactivo_id } = req.params;
  const resultado = await servicio.desasociarDeVersion(instrumento_id, Number(version), reactivo_id);
  responderUno(req, res, "reactivo", resultado);
});
