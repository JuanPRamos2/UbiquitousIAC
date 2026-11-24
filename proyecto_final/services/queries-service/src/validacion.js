import {
  exigirRango,
  leerBooleano,
  leerEnumeracion,
  leerFecha,
  leerId,
  leerOrden,
  leerPaginacion,
  leerTexto,
} from "../../comun/src/paginacion.js";

const ESTADOS_CAMPANIA = ["BORRADOR", "ABIERTA", "CERRADA", "CANCELADA"];
const TIPOS_UNIDAD = ["DIRECCION", "AREA", "DEPARTAMENTO", "TURNO", "EQUIPO"];
const ESTADOS_INTERVENCION = ["PROPUESTA", "APROBADA", "EN_EJECUCION", "FINALIZADA", "CANCELADA"];
const RESULTADOS_AUDITORIA = ["EXITO", "RECHAZADO", "GRUPO_INSUFICIENTE", "PRESUPUESTO_AGOTADO", "ERROR_TECNICO"];
const ESTADOS_PUBLICACION = ["PUBLICADO", "GRUPO_INSUFICIENTE", "PRESUPUESTO_PRIVACIDAD_AGOTADO"];
const ESTADOS_SOLICITUD = ["ABIERTA", "ATENDIDA", "CERRADA"];

const SORT_CAMPANIA = {
  secuencia: "c.secuencia",
  nombre: "c.nombre",
  fecha_inicio: "c.fecha_inicio",
};
const SORT_UNIDAD = {
  nombre: "u.nombre",
  nivel_jerarquico: "u.nivel_jerarquico",
  plantilla_declarada: "u.plantilla_declarada",
};
const SORT_INTERVENCION = {
  estado: "p.estado",
  fecha_inicio: "p.fecha_inicio",
  unidad: "u.nombre",
};

export function filtrosCampania(origen) {
  const paginacion = leerPaginacion(origen);
  const orden = leerOrden(origen, SORT_CAMPANIA, "secuencia");
  return {
    ...paginacion,
    ...orden,
    estado: leerEnumeracion(origen.estado, "estado", ESTADOS_CAMPANIA),
    search: leerTexto(origen.search, "search"),
  };
}

export function filtrosUnidad(origen) {
  const paginacion = leerPaginacion(origen);
  const orden = leerOrden(origen, SORT_UNIDAD, "nombre");
  return {
    ...paginacion,
    ...orden,
    tipo: leerEnumeracion(origen.tipo, "tipo", TIPOS_UNIDAD),
    activa: leerBooleano(origen.activa, "activa"),
    search: leerTexto(origen.search, "search"),
  };
}

export function filtrosInstrumento(origen) {
  return { ...leerPaginacion(origen), search: leerTexto(origen.search, "search") };
}

export function filtrosFuente(origen) {
  return {
    ...leerPaginacion(origen),
    search: leerTexto(origen.search, "search"),
    autorizada: leerBooleano(origen.autorizada, "autorizada"),
  };
}

export function filtrosIntervencion(origen) {
  const paginacion = leerPaginacion(origen);
  const orden = leerOrden(origen, SORT_INTERVENCION, "fecha_inicio");
  return {
    ...paginacion,
    ...orden,
    estado: leerEnumeracion(origen.estado, "estado", ESTADOS_INTERVENCION),
    unidad_organizacional_id: leerId(origen.unidad_organizacional_id, "unidad_organizacional_id"),
    search: leerTexto(origen.search, "search", 200),
  };
}

export function filtrosAuditoria(origen) {
  const desde = leerFecha(origen.desde, "desde");
  const hasta = leerFecha(origen.hasta, "hasta");
  exigirRango(desde, hasta);
  return {
    ...leerPaginacion(origen),
    accion: leerTexto(origen.accion, "accion", 60),
    resultado: leerEnumeracion(origen.resultado, "resultado", RESULTADOS_AUDITORIA),
    desde,
    hasta,
    search: leerTexto(origen.search, "search"),
  };
}

export function filtrosResultado(origen) {
  return {
    ...leerPaginacion(origen),
    unidad_organizacional_id: leerId(origen.unidad_organizacional_id, "unidad_organizacional_id"),
    campania_id: leerId(origen.campania_id, "campania_id"),
    estado: leerEnumeracion(origen.estado, "estado", ESTADOS_PUBLICACION),
  };
}

export function filtrosPresupuesto(origen) {
  return {
    ...leerPaginacion(origen),
    unidad_organizacional_id: leerId(origen.unidad_organizacional_id, "unidad_organizacional_id"),
    campania_id: leerId(origen.campania_id, "campania_id"),
    agotado: leerBooleano(origen.agotado, "agotado"),
  };
}

export function filtrosSolicitud(origen) {
  return {
    ...leerPaginacion(origen),
    estado: leerEnumeracion(origen.estado, "estado", ESTADOS_SOLICITUD),
    search: leerTexto(origen.search, "search", 200),
  };
}
