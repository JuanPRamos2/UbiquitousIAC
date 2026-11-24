import { exigirRango, leerFecha, leerId } from "../../comun/src/paginacion.js";

export function filtrosTendencia(origen) {
  const desde = leerFecha(origen.desde, "desde");
  const hasta = leerFecha(origen.hasta, "hasta");
  exigirRango(desde, hasta);
  return {
    unidad_organizacional_id: leerId(origen.unidad_organizacional_id, "unidad_organizacional_id"),
    dimension_id: leerId(origen.dimension_id, "dimension_id"),
    desde,
    hasta,
  };
}

export function filtrosPeriodo(origen) {
  const desde = leerFecha(origen.desde, "desde");
  const hasta = leerFecha(origen.hasta, "hasta");
  exigirRango(desde, hasta);
  return { desde, hasta };
}
