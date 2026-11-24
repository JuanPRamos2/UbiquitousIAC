/**
 * Historial de consentimiento visible: solo metadatos.
 * Nunca incluye empleado_id, correo, nombre ni IP.
 */
export function historialConsentimientoPublico(filas) {
  return filas.map((fila) => ({
    seudonimo_id: fila.seudonimo_id,
    version_consentimiento_id: fila.version_consentimiento_id,
    fecha_aceptacion: fila.fecha_aceptacion,
    fecha_revocacion: fila.fecha_revocacion,
    estado: fila.estado,
  }));
}
