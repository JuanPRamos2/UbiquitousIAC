/**
 * RN-04: no se publican métricas ni conteos individuales si n < k.
 * Nunca incluye seudonimo_id, empleado_id ni respuestas crudas.
 */
export function publicarAgregado({ total, k, promedioGlobal, detalle }) {
  if (total < k) {
    return {
      visible: false,
      motivo: "GRUPO_INSUFICIENTE",
      k,
    };
  }
  return {
    visible: true,
    k,
    total_respuestas: total,
    promedio_global: promedioGlobal,
    detalle,
  };
}

export function payloadPublicoUsuario({ usuario_id, perfil, seudonimo_id }) {
  const out = { usuario_id, perfil };
  if (seudonimo_id) out.seudonimo_id = seudonimo_id;
  return out;
}
