import { Router } from "express";
import { asyncHandler } from "../../../comun/src/errores.js";
import { exito } from "../../../comun/src/http.js";
import { leerEnteroId, leerId } from "../../../comun/src/paginacion.js";
import { PERFILES, PERFILES_AGREGADO, PERFILES_AUDITORIA, PERFILES_ORGANIZACION } from "../../../comun/src/perfiles.js";
import { afirmarXmlValido, directorioXsd, leerXsd } from "../../../comun/src/xsd.js";
import {
  filtrosAuditoria,
  filtrosCampania,
  filtrosFuente,
  filtrosInstrumento,
  filtrosIntervencion,
  filtrosPresupuesto,
  filtrosResultado,
  filtrosSolicitud,
  filtrosUnidad,
} from "../validacion.js";

const xsdDir = directorioXsd();
const rolesCatalogo = "COLABORADOR, LIDER, ESPECIALISTA, AUDITOR o ADMINISTRADOR";
const rolesOrganizacion = "LIDER (solo su unidad), ESPECIALISTA, AUDITOR o ADMINISTRADOR";
const rolesAuditoria = "AUDITOR o ADMINISTRADOR";

function validarEntrada(req, esquema) {
  if (req.formatoEntrada === "xml") afirmarXmlValido(req.bodyXml, leerXsd(xsdDir, esquema));
}

async function campanias(req, res) {
  const filtros = filtrosCampania(req.query);
  const resultado = await req.app.locals.servicio.campanias(req.actor, filtros);
  exito(req, res, {
    message: "Campañas consultadas",
    data: { campanias: resultado.filas },
    pagination: resultado.pagination,
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function buscarCampanias(req, res) {
  validarEntrada(req, "busqueda-campanias.xsd");
  const filtros = filtrosCampania(req.body || {});
  const resultado = await req.app.locals.servicio.campanias(req.actor, filtros);
  exito(req, res, {
    message: "Campañas consultadas",
    data: { campanias: resultado.filas },
    pagination: resultado.pagination,
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function campania(req, res) {
  const id = leerId(req.params.campaniaId, "campaniaId", { requerido: true });
  const resultado = await req.app.locals.servicio.campania(req.actor, id);
  exito(req, res, {
    message: "Campaña consultada",
    data: { campania: resultado.fila },
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function unidades(req, res) {
  const filtros = filtrosUnidad(req.query);
  const resultado = await req.app.locals.servicio.unidades(req.actor, filtros);
  exito(req, res, {
    message: "Unidades consultadas",
    data: { unidades: resultado.filas },
    pagination: resultado.pagination,
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function unidad(req, res) {
  const id = leerId(req.params.unidadId, "unidadId", { requerido: true });
  const resultado = await req.app.locals.servicio.unidad(req.actor, id);
  exito(req, res, {
    message: "Unidad consultada",
    data: { unidad: resultado.fila },
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function instrumentos(req, res) {
  const filtros = filtrosInstrumento(req.query);
  const resultado = await req.app.locals.servicio.instrumentos(req.actor, filtros);
  exito(req, res, {
    message: "Instrumentos consultados",
    data: { instrumentos: resultado.filas },
    pagination: resultado.pagination,
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function fuentes(req, res) {
  const filtros = filtrosFuente(req.query);
  const resultado = await req.app.locals.servicio.fuentes(req.actor, filtros);
  exito(req, res, {
    message: "Fuentes consultadas",
    data: { fuentes: resultado.filas },
    pagination: resultado.pagination,
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function intervenciones(req, res) {
  const filtros = filtrosIntervencion(req.query);
  const resultado = await req.app.locals.servicio.intervenciones(req.actor, filtros);
  exito(req, res, {
    message: "Intervenciones consultadas",
    data: { intervenciones: resultado.filas },
    pagination: resultado.pagination,
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function intervencion(req, res) {
  const id = leerEnteroId(req.params.intervencionId, "intervencionId");
  const resultado = await req.app.locals.servicio.intervencion(req.actor, id);
  exito(req, res, {
    message: "Intervención consultada",
    data: { intervencion: resultado.fila },
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function auditoria(req, res) {
  const filtros = filtrosAuditoria(req.query);
  const resultado = await req.app.locals.servicio.auditoria(req.actor, filtros);
  exito(req, res, {
    message: "Bitácora consultada",
    data: { eventos: resultado.filas },
    pagination: resultado.pagination,
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function buscarAuditoria(req, res) {
  validarEntrada(req, "busqueda-auditoria.xsd");
  const filtros = filtrosAuditoria(req.body || {});
  const resultado = await req.app.locals.servicio.auditoria(req.actor, filtros);
  exito(req, res, {
    message: "Bitácora consultada",
    data: { eventos: resultado.filas },
    pagination: resultado.pagination,
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function resultados(req, res) {
  const filtros = filtrosResultado(req.query);
  const resultado = await req.app.locals.servicio.resultados(req.actor, filtros);
  exito(req, res, {
    message: "Resultados protegidos consultados",
    data: { resultados: resultado.filas },
    pagination: resultado.pagination,
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function presupuesto(req, res) {
  const filtros = filtrosPresupuesto(req.query);
  const resultado = await req.app.locals.servicio.presupuesto(req.actor, filtros);
  exito(req, res, {
    message: "Presupuesto de privacidad consultado",
    data: { presupuestos: resultado.filas },
    pagination: resultado.pagination,
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function solicitudes(req, res) {
  const filtros = filtrosSolicitud(req.query);
  const resultado = await req.app.locals.servicio.solicitudes(req.actor, filtros);
  exito(req, res, {
    message: "Solicitudes de apoyo consultadas",
    data: { solicitudes: resultado.filas },
    pagination: resultado.pagination,
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function participacion(req, res) {
  const resultado = await req.app.locals.servicio.participacion(req.actor);
  exito(req, res, {
    message: "Participación propia consultada",
    data: { participacion: resultado.fila },
    cache: resultado.cache,
    clave: resultado.clave,
  });
}

async function observabilidad(req, res) {
  const consultas = await req.app.locals.servicio.observabilidad();
  exito(req, res, {
    message: "Contador de consultas",
    data: { contador: consultas },
    cache: "BYPASS",
  });
}

const pagina = [
  { name: "page", in: "query", description: "Página, desde 1", schema: { type: "integer", minimum: 1 }, example: 1 },
  { name: "limit", in: "query", description: "Tamaño de página, máximo 100", schema: { type: "integer", minimum: 1, maximum: 100 }, example: 20 },
];

const ejemploCampania = {
  campania_id: "CAMP-2026-S4",
  nombre: "Medicion semana 4",
  estado: "ABIERTA",
  fecha_inicio: "2026-08-24",
  fecha_fin: "2026-08-28",
  secuencia: 4,
  instrumento_id: "INST-BIENESTAR",
  version_instrumento: 1,
  activa: true,
};

const ejemploListado = {
  success: true,
  message: "Campañas consultadas",
  data: { campanias: [ejemploCampania] },
  pagination: { page: 1, limit: 20, total: 4, totalPages: 1 },
  meta: { cache: "MISS", servicio: "queries-service", correlacion_id: "demo", clave_cache: "cache:queries:campanias:demo" },
};

export const operaciones = [
  { id: "listarCampanias", metodo: "get", ruta: "/campanias", tag: "Campañas", roles: rolesCatalogo, perfiles: Object.values(PERFILES), resumen: "Listar campañas", descripcion: "Consulta paginada del catálogo de campañas de bienestar. No devuelve respuestas individuales.", parametros: [...pagina, { name: "search", in: "query", description: "Texto del nombre", schema: { type: "string" } }, { name: "estado", in: "query", description: "BORRADOR, ABIERTA, CERRADA o CANCELADA", schema: { type: "string" }, example: "ABIERTA" }, { name: "sort", in: "query", description: "secuencia, nombre o fecha_inicio", schema: { type: "string" }, example: "secuencia" }, { name: "order", in: "query", description: "asc o desc", schema: { type: "string" }, example: "desc" }], handler: campanias, ejemplo: ejemploListado },
  { id: "buscarCampanias", metodo: "post", ruta: "/campanias/buscar", tag: "Campañas", roles: rolesCatalogo, perfiles: Object.values(PERFILES), resumen: "Buscar campañas con cuerpo JSON o XML", descripcion: "Misma consulta que el listado, cuando los filtros viajan en el cuerpo. Acepta application/json y application/xml.", cuerpo: { search: "semana", estado: "ABIERTA", page: 1, limit: 20, sort: "fecha_inicio", order: "desc" }, cuerpoXml: "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<busqueda><search>semana</search><estado>ABIERTA</estado><page>1</page><limit>20</limit><sort>fecha_inicio</sort><order>desc</order></busqueda>", handler: buscarCampanias, ejemplo: ejemploListado },
  { id: "obtenerCampania", metodo: "get", ruta: "/campanias/:campaniaId", tag: "Campañas", roles: rolesCatalogo, perfiles: Object.values(PERFILES), resumen: "Obtener una campaña", descripcion: "Regresa 404 si el identificador no existe.", parametros: [{ name: "campaniaId", in: "path", required: true, description: "Identificador de campaña", schema: { type: "string" }, example: "CAMP-2026-S4" }], handler: campania, ejemplo: { success: true, message: "Campaña consultada", data: { campania: ejemploCampania }, meta: { cache: "MISS", servicio: "queries-service" } } },
  { id: "listarUnidades", metodo: "get", ruta: "/unidades", tag: "Organización", roles: rolesCatalogo, perfiles: Object.values(PERFILES), resumen: "Listar unidades organizacionales", descripcion: "Catálogo de áreas y turnos. No incluye personas ni respuestas.", parametros: [...pagina, { name: "search", in: "query", schema: { type: "string" }, description: "Texto del nombre" }, { name: "tipo", in: "query", schema: { type: "string" }, description: "DIRECCION, AREA, DEPARTAMENTO, TURNO o EQUIPO" }, { name: "activa", in: "query", schema: { type: "boolean" }, description: "true o false" }, { name: "sort", in: "query", schema: { type: "string" }, description: "nombre, nivel_jerarquico o plantilla_declarada" }, { name: "order", in: "query", schema: { type: "string" }, description: "asc o desc" }], handler: unidades, ejemplo: { success: true, message: "Unidades consultadas", data: { unidades: [{ unidad_organizacional_id: "UO-CC-TURNO-B", nombre: "Call Center - Turno B", tipo: "TURNO", activa: true }] }, pagination: { page: 1, limit: 20, total: 4, totalPages: 1 }, meta: { cache: "MISS", servicio: "queries-service" } } },
  { id: "obtenerUnidad", metodo: "get", ruta: "/unidades/:unidadId", tag: "Organización", roles: rolesCatalogo, perfiles: Object.values(PERFILES), resumen: "Obtener una unidad", descripcion: "Regresa 404 si la unidad no existe.", parametros: [{ name: "unidadId", in: "path", required: true, schema: { type: "string" }, description: "Identificador de unidad", example: "UO-CC-TURNO-B" }], handler: unidad, ejemplo: { success: true, message: "Unidad consultada", data: { unidad: { unidad_organizacional_id: "UO-CC-TURNO-B", nombre: "Call Center - Turno B", tipo: "TURNO" } }, meta: { cache: "HIT", servicio: "queries-service" } } },
  { id: "listarInstrumentos", metodo: "get", ruta: "/instrumentos", tag: "Catálogo", roles: rolesCatalogo, perfiles: Object.values(PERFILES), resumen: "Listar instrumentos", descripcion: "Instrumentos de bienestar activos.", parametros: pagina, handler: instrumentos, ejemplo: { success: true, message: "Instrumentos consultados", data: { instrumentos: [{ instrumento_id: "INST-BIENESTAR", nombre: "Instrumento breve de bienestar laboral", tipo: "NOM035", activo: true }] }, pagination: { page: 1, limit: 20, total: 1, totalPages: 1 }, meta: { cache: "MISS", servicio: "queries-service" } } },
  { id: "listarFuentes", metodo: "get", ruta: "/fuentes", tag: "Catálogo", roles: rolesCatalogo, perfiles: Object.values(PERFILES), resumen: "Listar fuentes autorizadas y prohibidas", descripcion: "Muestra qué fuentes pueden alimentar indicadores y cuáles están prohibidas por vigilancia.", parametros: [...pagina, { name: "autorizada", in: "query", schema: { type: "boolean" }, description: "true solo autorizadas, false solo prohibidas" }, { name: "search", in: "query", schema: { type: "string" }, description: "Texto del nombre" }], handler: fuentes, ejemplo: { success: true, message: "Fuentes consultadas", data: { fuentes: [{ fuente_id: "FA-AUTOREPORTE", nombre: "Autoreporte de la persona", autorizada: true, motivo: "Declarado y consentido por la persona." }] }, pagination: { page: 1, limit: 20, total: 11, totalPages: 1 }, meta: { cache: "MISS", servicio: "queries-service" } } },
  { id: "listarIntervenciones", metodo: "get", ruta: "/intervenciones", tag: "Intervenciones", roles: rolesOrganizacion, perfiles: PERFILES_ORGANIZACION, resumen: "Listar planes de intervención organizacional", descripcion: "Planes sobre unidades, nunca sobre una persona. El líder solo ve su unidad.", parametros: [...pagina, { name: "estado", in: "query", schema: { type: "string" }, description: "PROPUESTA, APROBADA, EN_EJECUCION, FINALIZADA o CANCELADA" }, { name: "unidad_organizacional_id", in: "query", schema: { type: "string" }, description: "Unidad. El líder no puede pedir otra." }, { name: "search", in: "query", schema: { type: "string" }, description: "Texto de la justificación o del tipo" }, { name: "sort", in: "query", schema: { type: "string" }, description: "estado, fecha_inicio o unidad" }, { name: "order", in: "query", schema: { type: "string" }, description: "asc o desc" }], handler: intervenciones, ejemplo: { success: true, message: "Intervenciones consultadas", data: { intervenciones: [] }, pagination: { page: 1, limit: 20, total: 0, totalPages: 0 }, meta: { cache: "MISS", servicio: "queries-service" } } },
  { id: "obtenerIntervencion", metodo: "get", ruta: "/intervenciones/:intervencionId", tag: "Intervenciones", roles: rolesOrganizacion, perfiles: PERFILES_ORGANIZACION, resumen: "Obtener una intervención", descripcion: "404 si no existe. 403 si un líder pide la de otra unidad.", parametros: [{ name: "intervencionId", in: "path", required: true, schema: { type: "integer" }, description: "Identificador numérico", example: 1 }], handler: intervencion, ejemplo: { success: true, message: "Intervención consultada", data: { intervencion: { intervencion_id: "1", estado: "PROPUESTA" } }, meta: { cache: "MISS", servicio: "queries-service" } } },
  { id: "listarAuditoria", metodo: "get", ruta: "/auditoria", tag: "Auditoría", roles: rolesAuditoria, perfiles: PERFILES_AUDITORIA, resumen: "Consultar la bitácora", descripcion: "Quién accedió, a qué recurso y con qué resultado. No incluye el contenido de ninguna respuesta.", parametros: [...pagina, { name: "accion", in: "query", schema: { type: "string" }, description: "Código de acción" }, { name: "resultado", in: "query", schema: { type: "string" }, description: "EXITO, RECHAZADO, GRUPO_INSUFICIENTE, PRESUPUESTO_AGOTADO o ERROR_TECNICO" }, { name: "desde", in: "query", schema: { type: "string", format: "date" }, description: "YYYY-MM-DD" }, { name: "hasta", in: "query", schema: { type: "string", format: "date" }, description: "YYYY-MM-DD" }, { name: "search", in: "query", schema: { type: "string" }, description: "Actor, correlación o acción" }], handler: auditoria, ejemplo: { success: true, message: "Bitácora consultada", data: { eventos: [{ accion: "LOGIN_EXITOSO", resultado: "EXITO", actor_perfil: "COLABORADOR" }] }, pagination: { page: 1, limit: 20, total: 14, totalPages: 1 }, meta: { cache: "MISS", servicio: "queries-service" } } },
  { id: "buscarAuditoria", metodo: "post", ruta: "/auditoria/buscar", tag: "Auditoría", roles: rolesAuditoria, perfiles: PERFILES_AUDITORIA, resumen: "Buscar en la bitácora con JSON o XML", descripcion: "Filtros de auditoría en el cuerpo. Acepta application/json y application/xml.", cuerpo: { accion: "AGREGADO_CONSULTADO", resultado: "EXITO", desde: "2026-08-01", hasta: "2026-08-31", page: 1, limit: 20 }, cuerpoXml: "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<busqueda><accion>AGREGADO_CONSULTADO</accion><resultado>EXITO</resultado><desde>2026-08-01</desde><hasta>2026-08-31</hasta><page>1</page><limit>20</limit></busqueda>", handler: buscarAuditoria, ejemplo: { success: true, message: "Bitácora consultada", data: { eventos: [] }, pagination: { page: 1, limit: 20, total: 0, totalPages: 0 }, meta: { cache: "MISS", servicio: "queries-service" } } },
  { id: "listarResultados", metodo: "get", ruta: "/resultados-protegidos", tag: "Privacidad", roles: rolesOrganizacion, perfiles: PERFILES_AGREGADO, resumen: "Consultar resultados ya publicados", descripcion: "Lee la vista agregado.v_tablero_unidad. No calcula de nuevo y no muestra el n exacto ni respuestas crudas. El líder queda limitado a su unidad.", parametros: [...pagina, { name: "unidad_organizacional_id", in: "query", schema: { type: "string" }, description: "Unidad" }, { name: "campania_id", in: "query", schema: { type: "string" }, description: "Campaña" }, { name: "estado", in: "query", schema: { type: "string" }, description: "PUBLICADO, GRUPO_INSUFICIENTE o PRESUPUESTO_PRIVACIDAD_AGOTADO" }], handler: resultados, ejemplo: { success: true, message: "Resultados protegidos consultados", data: { resultados: [] }, pagination: { page: 1, limit: 20, total: 0, totalPages: 0 }, meta: { cache: "MISS", servicio: "queries-service" } } },
  { id: "listarPresupuesto", metodo: "get", ruta: "/presupuesto", tag: "Privacidad", roles: rolesOrganizacion, perfiles: PERFILES_AGREGADO, resumen: "Consultar el presupuesto de privacidad", descripcion: "Epsilon consumido y restante por campaña y unidad. El líder solo ve su unidad.", parametros: [...pagina, { name: "unidad_organizacional_id", in: "query", schema: { type: "string" }, description: "Unidad" }, { name: "campania_id", in: "query", schema: { type: "string" }, description: "Campaña" }, { name: "agotado", in: "query", schema: { type: "boolean" }, description: "true o false" }], handler: presupuesto, ejemplo: { success: true, message: "Presupuesto de privacidad consultado", data: { presupuestos: [] }, pagination: { page: 1, limit: 20, total: 0, totalPages: 0 }, meta: { cache: "MISS", servicio: "queries-service" } } },
  { id: "listarSolicitudes", metodo: "get", ruta: "/solicitudes-apoyo", tag: "MongoDB", roles: rolesAuditoria, perfiles: PERFILES_AUDITORIA, resumen: "Consultar solicitudes de apoyo", descripcion: "Lee MongoDB solicitudes_apoyo. Omite el seudónimo, igual que el listado de auditoría del monolito.", parametros: [...pagina, { name: "estado", in: "query", schema: { type: "string" }, description: "ABIERTA, ATENDIDA o CERRADA" }, { name: "search", in: "query", schema: { type: "string" }, description: "Texto del mensaje" }], handler: solicitudes, ejemplo: { success: true, message: "Solicitudes de apoyo consultadas", data: { solicitudes: [] }, pagination: { page: 1, limit: 20, total: 0, totalPages: 0 }, meta: { cache: "MISS", servicio: "queries-service" } } },
  { id: "miParticipacion", metodo: "get", ruta: "/mi-participacion", tag: "Portal", roles: "COLABORADOR", perfiles: [PERFILES.COLABORADOR], resumen: "Consultar la participación propia", descripcion: "Usa portal.v_participacion_propia filtrada por el usuario de la sesión. No devuelve el seudónimo ni puntajes.", handler: participacion, ejemplo: { success: true, message: "Participación propia consultada", data: { participacion: { estado_consentimiento: "ACEPTADO", campanias_respondidas: 4 } }, meta: { cache: "MISS", servicio: "queries-service" } } },
  { id: "observabilidadConsultas", metodo: "get", ruta: "/observabilidad", tag: "Redis", roles: "ADMINISTRADOR", perfiles: [PERFILES.ADMINISTRADOR], resumen: "Leer el contador de consultas", descripcion: "Devuelve counter:queries:consultas sin recorrer Redis con KEYS.", handler: observabilidad, ejemplo: { success: true, message: "Contador de consultas", data: { contador: { clave: "counter:queries:consultas", valor: 1, ttl: -1 } }, meta: { cache: "BYPASS", servicio: "queries-service" } } },
];

export function consultasRouter(autorizar) {
  const router = Router();
  for (const op of operaciones) {
    router[op.metodo](op.ruta, autorizar(...op.perfiles), asyncHandler(op.handler));
  }
  return router;
}
