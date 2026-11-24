/**
 * Constructores puros de tuberias de agregacion.
 *
 * Son funciones sin efectos: reciben filtros y devuelven el arreglo de
 * etapas. Eso permite probarlas sin MongoDB y, sobre todo, revisarlas:
 * una tuberia escrita en linea dentro de un controlador no se puede
 * inspeccionar en una prueba.
 */

/** Respuestas agrupadas por unidad y campania. */
export function tuberiaRespuestasPorUnidadCampania({ campania_id, desde, hasta } = {}) {
  const coincide = {};
  if (campania_id) coincide.campania_id = campania_id;
  if (desde || hasta) {
    coincide.fecha = {};
    if (desde) coincide.fecha.$gte = new Date(desde);
    if (hasta) coincide.fecha.$lte = new Date(hasta);
  }
  const etapas = [];
  if (Object.keys(coincide).length) etapas.push({ $match: coincide });
  etapas.push(
    {
      $group: {
        _id: { unidad: "$unidad_organizacional_id", campania: "$campania_id" },
        respuestas: { $sum: 1 },
        primera: { $min: "$fecha" },
        ultima: { $max: "$fecha" },
      },
    },
    {
      $project: {
        _id: 0,
        unidad_organizacional_id: "$_id.unidad",
        campania_id: "$_id.campania",
        respuestas: 1, primera: 1, ultima: 1,
      },
    },
    { $sort: { campania_id: 1, unidad_organizacional_id: 1 } }
  );
  return etapas;
}

/** Conteo de la bitacora por tipo de accion. */
export function tuberiaBitacoraPorAccion({ desde, hasta } = {}) {
  const coincide = {};
  if (desde || hasta) {
    coincide.timestamp = {};
    if (desde) coincide.timestamp.$gte = new Date(desde);
    if (hasta) coincide.timestamp.$lte = new Date(hasta);
  }
  const etapas = [];
  if (Object.keys(coincide).length) etapas.push({ $match: coincide });
  etapas.push(
    { $group: { _id: "$accion", veces: { $sum: 1 }, ultima: { $max: "$timestamp" } } },
    { $project: { _id: 0, accion: "$_id", veces: 1, ultima: 1 } },
    { $sort: { veces: -1 } }
  );
  return etapas;
}

/** Eventos de proceso agrupados por tipo. */
export function tuberiaEventosPorTipo({ desde, hasta } = {}) {
  const coincide = {};
  if (desde || hasta) {
    coincide.timestamp = {};
    if (desde) coincide.timestamp.$gte = new Date(desde);
    if (hasta) coincide.timestamp.$lte = new Date(hasta);
  }
  const etapas = [];
  if (Object.keys(coincide).length) etapas.push({ $match: coincide });
  etapas.push(
    { $group: { _id: "$tipo", veces: { $sum: 1 }, ultima: { $max: "$timestamp" } } },
    { $project: { _id: 0, tipo: "$_id", veces: 1, ultima: 1 } },
    { $sort: { veces: -1 } }
  );
  return etapas;
}
