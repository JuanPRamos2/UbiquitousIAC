import { Router } from "express";
import { asyncHandler } from "../../../comun/src/errores.js";
import { exito } from "../../../comun/src/http.js";
import {
  PERFILES,
  PERFILES_AUDITORIA,
  PERFILES_ORGANIZACION,
  TODOS_LOS_PERFILES,
} from "../../../comun/src/perfiles.js";
import { afirmarXmlValido, directorioXsd, leerXsd } from "../../../comun/src/xsd.js";
import { filtrosPeriodo, filtrosTendencia } from "../validacion.js";

const xsdDir = directorioXsd();
const rolesOrganizacion = "LIDER (solo su unidad), ESPECIALISTA, AUDITOR o ADMINISTRADOR";
const rolesAuditoria = "AUDITOR o ADMINISTRADOR";
const rolesCatalogo = "Cualquier perfil autenticado";

function validarEntrada(req) {
  if (req.formatoEntrada === "xml") afirmarXmlValido(req.bodyXml, leerXsd(xsdDir, "reporte-tendencia.xsd"));
}

async function emitir(req, res, message, resultado) {
  exito(req, res, {
    message,
    data: resultado.data,
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function resumen(req, res) {
  emitir(req, res, "Resumen generado", await req.app.locals.servicio.resumen(req.actor));
}
async function campanias(req, res) {
  emitir(req, res, "Distribución de campañas", await req.app.locals.servicio.campaniasPorEstado(req.actor));
}
async function intervenciones(req, res) {
  emitir(req, res, "Distribución de intervenciones", await req.app.locals.servicio.intervencionesPorEstado(req.actor));
}
async function reglas(req, res) {
  emitir(req, res, "Reglas por nivel", await req.app.locals.servicio.reglasPorNivel(req.actor));
}
async function fuentes(req, res) {
  emitir(req, res, "Fuentes autorizadas y prohibidas", await req.app.locals.servicio.fuentes(req.actor));
}
async function tendencia(req, res) {
  const filtros = filtrosTendencia(req.query);
  emitir(req, res, "Tendencia de participación protegida", await req.app.locals.servicio.tendencia(req.actor, filtros));
}
async function tendenciaCuerpo(req, res) {
  validarEntrada(req);
  const filtros = filtrosTendencia(req.body || {});
  emitir(req, res, "Tendencia de participación protegida", await req.app.locals.servicio.tendencia(req.actor, filtros));
}
async function auditoriaAccion(req, res) {
  const filtros = filtrosPeriodo(req.query);
  emitir(req, res, "Auditoría por acción", await req.app.locals.servicio.auditoriaPorAccion(req.actor, filtros));
}
async function auditoriaPeriodo(req, res) {
  const filtros = filtrosPeriodo(req.query);
  emitir(req, res, "Auditoría por periodo", await req.app.locals.servicio.auditoriaPorPeriodo(req.actor, filtros));
}
async function publicacion(req, res) {
  emitir(req, res, "Distribución de publicación", await req.app.locals.servicio.publicacion(req.actor));
}
async function solicitudes(req, res) {
  emitir(req, res, "Solicitudes de apoyo", await req.app.locals.servicio.solicitudes(req.actor));
}
async function observabilidad(req, res) {
  const contador = await req.app.locals.servicio.observabilidad();
  exito(req, res, { message: "Contador de reportes", data: { contador }, cache: "BYPASS" });
}

const ejemplo = {
  success: true,
  message: "Distribución de campañas",
  data: {
    categories: ["ABIERTA", "CERRADA"],
    series: [{ name: "Campañas", data: [1, 3] }],
    nota: "Ejemplo de forma. Al ejecutar, los números salen de un conteo en PostgreSQL y cambian si cambian las campañas.",
  },
  meta: { cache: "MISS", servicio: "reports-service", clave_cache: "cache:reports:campanias-estado:demo" },
};

const parametrosPeriodo = [
  { name: "desde", in: "query", schema: { type: "string", format: "date" }, description: "YYYY-MM-DD" },
  { name: "hasta", in: "query", schema: { type: "string", format: "date" }, description: "YYYY-MM-DD" },
];

export const operaciones = [
  { id: "resumen", metodo: "get", ruta: "/resumen", tag: "Resumen", roles: rolesOrganizacion, perfiles: PERFILES_ORGANIZACION, resumen: "Totales operativos", descripcion: "Conteos reales de campañas, unidades, intervenciones y resultados protegidos, listos para Highcharts. El líder queda acotado a su unidad. La auditoría solo se suma para auditor y administrador.", handler: resumen, ejemplo },
  { id: "campaniasEstado", metodo: "get", ruta: "/campanias-por-estado", tag: "Campañas", roles: rolesCatalogo, perfiles: TODOS_LOS_PERFILES, resumen: "Campañas por estado", descripcion: "Cuenta las campañas que existen en PostgreSQL, agrupadas por estado. Los valores no están fijos: si se abre, cierra o agrega una campaña, la serie cambia. El ejemplo 1 y 3 solo ilustra la forma de la respuesta.", handler: campanias, ejemplo },
  { id: "intervencionesEstado", metodo: "get", ruta: "/intervenciones-por-estado", tag: "Intervenciones", roles: rolesOrganizacion, perfiles: PERFILES_ORGANIZACION, resumen: "Intervenciones por estado", descripcion: "Planes organizacionales agrupados. Si no hay planes, la serie queda vacía.", handler: intervenciones, ejemplo },
  { id: "reglasNivel", metodo: "get", ruta: "/reglas-por-nivel", tag: "Riesgo", roles: rolesOrganizacion, perfiles: PERFILES_ORGANIZACION, resumen: "Reglas de riesgo por nivel", descripcion: "Cuenta reglas activas por nivel. No evalúa a una persona.", handler: reglas, ejemplo },
  { id: "fuentes", metodo: "get", ruta: "/fuentes", tag: "Gobernanza", roles: rolesCatalogo, perfiles: TODOS_LOS_PERFILES, resumen: "Fuentes autorizadas frente a prohibidas", descripcion: "Agrupa catalogo.fuente_autorizada. Útil para explicar qué datos están prohibidos.", handler: fuentes, ejemplo },
  { id: "tendencia", metodo: "get", ruta: "/tendencia", tag: "Tendencia", roles: rolesOrganizacion, perfiles: PERFILES_ORGANIZACION, resumen: "Tendencia protegida por campaña", descripcion: "Serie de participación suficiente (1 o vacío si el grupo no alcanza k) y valor protegido ya publicado. No devuelve el n exacto ni recalcula el ruido.", parametros: [{ name: "unidad_organizacional_id", in: "query", schema: { type: "string" }, description: "Unidad. Obligatoria de facto para el líder." }, { name: "dimension_id", in: "query", schema: { type: "string" }, description: "Dimensión publicada. Vacío usa el índice global." }], handler: tendencia, ejemplo },
  { id: "tendenciaCuerpo", metodo: "post", ruta: "/tendencia", tag: "Tendencia", roles: rolesOrganizacion, perfiles: PERFILES_ORGANIZACION, resumen: "Tendencia con filtros JSON o XML", descripcion: "El mismo reporte cuando la unidad, la dimensión y el periodo viajan en el cuerpo.", cuerpo: { unidad_organizacional_id: "UO-CC-TURNO-B", dimension_id: "DIM-CARGA" }, cuerpoXml: "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<reporte><unidad_organizacional_id>UO-CC-TURNO-B</unidad_organizacional_id><dimension_id>DIM-CARGA</dimension_id></reporte>", handler: tendenciaCuerpo, ejemplo },
  { id: "auditoriaAccion", metodo: "get", ruta: "/auditoria-por-accion", tag: "Auditoría", roles: rolesAuditoria, perfiles: PERFILES_AUDITORIA, resumen: "Eventos de auditoría por acción", descripcion: "Conteo de auditoria.bitacora agrupado por acción.", parametros: parametrosPeriodo, handler: auditoriaAccion, ejemplo },
  { id: "auditoriaPeriodo", metodo: "get", ruta: "/auditoria-por-periodo", tag: "Auditoría", roles: rolesAuditoria, perfiles: PERFILES_AUDITORIA, resumen: "Eventos de auditoría por día", descripcion: "Serie temporal para Highcharts. desde y hasta son opcionales.", parametros: parametrosPeriodo, handler: auditoriaPeriodo, ejemplo },
  { id: "publicacion", metodo: "get", ruta: "/publicacion", tag: "Privacidad", roles: rolesOrganizacion, perfiles: PERFILES_ORGANIZACION, resumen: "Distribución de estados de publicación", descripcion: "Lee resultados ya almacenados. No invoca el mecanismo de Laplace ni gasta presupuesto.", handler: publicacion, ejemplo },
  { id: "solicitudes", metodo: "get", ruta: "/solicitudes-apoyo", tag: "MongoDB", roles: rolesAuditoria, perfiles: PERFILES_AUDITORIA, resumen: "Solicitudes de apoyo por estado", descripcion: "Agregación de MongoDB. No incluye el seudónimo.", handler: solicitudes, ejemplo },
  { id: "observabilidadReportes", metodo: "get", ruta: "/observabilidad", tag: "Redis", roles: "ADMINISTRADOR", perfiles: [PERFILES.ADMINISTRADOR], resumen: "Leer el contador de reportes", descripcion: "Devuelve counter:reports:generados.", handler: observabilidad, ejemplo: { success: true, message: "Contador de reportes", data: { contador: { clave: "counter:reports:generados", valor: 1, ttl: -1 } }, meta: { cache: "BYPASS", servicio: "reports-service" } } },
];

export function reportesRouter(autorizar) {
  const router = Router();
  for (const op of operaciones) router[op.metodo](op.ruta, autorizar(...op.perfiles), asyncHandler(op.handler));
  return router;
}
