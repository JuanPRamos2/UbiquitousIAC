/**
 * Estructuras de Redis del diseño políglota. Los TTL se aplican al escribir.
 * La política completa, incluidas caché, rate limit y contadores de
 * queries-service y reports-service, está en services/comun/src/claves-redis.js.
 * session:{jti} y revoked:{jti} son el contrato con Auth Service.
 */
export function claveSesion(jti) {
  return `session:${jti}`;
}

export function claveRevocado(jti) {
  return `revoked:${jti}`;
}

export function claveLoginFallido(usuarioId) {
  return `contador:login_fallido:${usuarioId}`;
}

export function claveCacheAgregado(unidadId, campaniaId) {
  return `cache:agregado:${unidadId}:${campaniaId}`;
}

export function claveLockAgregado(unidadId) {
  return `lock:calculo_agregado:${unidadId}`;
}

export const PATRON_CACHE_AGREGADO = "cache:agregado:*";
