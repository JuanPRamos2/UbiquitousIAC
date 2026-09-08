/**
 * Documento de respuestas_encuesta: solo IDs operativos.
 * Nunca incluye empleado_id, correo, nombre ni IP.
 */
export function documentoRespuestaMongo({
  seudonimo_id,
  instrumento_id,
  version_instrumento,
  campania_id,
  unidad_organizacional_id,
  version_consentimiento,
  respuestas,
  fecha_respuesta = new Date(),
}) {
  return {
    seudonimo_id,
    instrumento_id,
    version_instrumento,
    campania_id,
    unidad_organizacional_id,
    version_consentimiento,
    fecha_respuesta,
    respuestas,
  };
}

export function historialConsentimientoPublico(filas) {
  return filas.map((fila) => ({
    seudonimo_id: fila.seudonimo_id,
    version_consentimiento_id: fila.version_consentimiento_id,
    fecha_aceptacion: fila.fecha_aceptacion,
    fecha_revocacion: fila.fecha_revocacion,
    estado: fila.estado,
  }));
}
