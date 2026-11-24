/**
 * Política de claves compartida.
 * Auth Service (hoy el monolito en /api/auth) escribe session:{jti} y revoked:{jti}.
 * ESTO SE DEBE CONECTAR CON AUTH SERVICE: no cambiar estos dos patrones.
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

export function claveCache(servicio, recurso, hash) {
  return `cache:${servicio}:${recurso}:${hash}`;
}

export function claveLockCache(servicio, recurso, hash) {
  return `lock:cache:${servicio}:${recurso}:${hash}`;
}

export function claveRateLimit(servicio, identidad, bucket) {
  return `ratelimit:${servicio}:${identidad}:${bucket}`;
}

export function claveContador(operacion) {
  return `counter:${operacion}`;
}

export function claveContadorDiario(operacion, dia) {
  return `counter:${operacion}:${dia}`;
}

export function claveContexto(usuarioId) {
  return `cache:auth:contexto:${usuarioId}`;
}

export const CATALOGO_CLAVES = [
  {
    patron: "session:{jti}",
    componente: "Auth Service (hoy el monolito, POST /api/auth/login)",
    proposito: "Sesión vigente del JWT. Los microservicios solo la consultan.",
    tipo: "hash",
    ttl: "JWT_EXPIRES_SEC (900 s por defecto), igual a la vida del token",
    seCrea: "En el login, junto con el JWT",
    seElimina: "En el logout o al vencer el TTL",
    consultan: "auth, queries-service, reports-service y cualquier servicio protegido",
  },
  {
    patron: "revoked:{jti}",
    componente: "Auth Service (hoy el monolito, POST /api/auth/logout)",
    proposito: "Token revocado antes de su expiración natural",
    tipo: "string",
    ttl: "Segundos que le quedan al JWT",
    seCrea: "En el logout",
    seElimina: "Al expirar el TTL; no se borra a mano",
    consultan: "Cualquier servicio que valide JWT",
  },
  {
    patron: "contador:login_fallido:{usuario_id}",
    componente: "Auth Service (monolito)",
    proposito: "Intentos fallidos de acceso",
    tipo: "string entero",
    ttl: "900 s",
    seCrea: "Primer login fallido",
    seElimina: "Al acertar la contraseña o al vencer el TTL",
    consultan: "Auth Service",
  },
  {
    patron: "cache:agregado:{unidad}:{campania}",
    componente: "Proceso principal de agregados (monolito)",
    proposito: "Resultado protegido ya calculado, sin repetir el gasto de privacidad",
    tipo: "string JSON",
    ttl: "REDIS_TTL_CACHE_AGREGADO_SEC (300 s)",
    seCrea: "Al publicar un agregado",
    seElimina: "TTL o invalidación cuando cambia k o se envía una respuesta",
    consultan: "El monolito. Queries y reports no reutilizan esta clave: leen las vistas publicadas.",
  },
  {
    patron: "lock:calculo_agregado:{unidad}",
    componente: "Proceso principal de agregados (monolito)",
    proposito: "Bloqueo distribuido del cálculo que consume presupuesto de privacidad",
    tipo: "string",
    ttl: "REDIS_TTL_LOCK_AGREGADO_SEC (10 s)",
    seCrea: "Antes de calcular un agregado en ausencia de caché",
    seElimina: "Al terminar el cálculo o al vencer el TTL si el proceso muere",
    consultan: "Solo el proceso que calcula agregados",
  },
  {
    patron: "cache:{servicio}:{recurso}:{hash}",
    componente: "queries-service y reports-service",
    proposito: "Caché de lecturas. El hash incluye filtros y alcance del actor.",
    tipo: "string JSON",
    ttl: "CACHE_TTL_SEC (60 s por defecto)",
    seCrea: "CACHE MISS, después de consultar PostgreSQL o MongoDB",
    seElimina: "Al vencer el TTL",
    consultan: "El servicio que la creó",
  },
  {
    patron: "lock:cache:{servicio}:{recurso}:{hash}",
    componente: "queries-service y reports-service",
    proposito: "Evita que varias peticiones simultáneas repitan la misma lectura pesada",
    tipo: "string",
    ttl: "REDIS_TTL_LOCK_SEC (10 s)",
    seCrea: "En CACHE MISS, con SET NX",
    seElimina: "Al guardar la caché o al vencer el TTL",
    consultan: "El servicio que está llenando esa caché",
  },
  {
    patron: "ratelimit:{servicio}:{identidad}:{ventana}",
    componente: "queries-service y reports-service",
    proposito: "Contador de peticiones por usuario o IP dentro de la ventana",
    tipo: "string entero",
    ttl: "RATE_LIMIT_WINDOW_SEC (60 s por defecto)",
    seCrea: "Primera petición de esa ventana",
    seElimina: "Al vencer la ventana",
    consultan: "El servicio que aplica el límite",
  },
  {
    patron: "counter:queries:consultas",
    componente: "queries-service",
    proposito: "Total de consultas respondidas con éxito",
    tipo: "string entero",
    ttl: "Sin TTL: es un contador operativo, no un dato temporal",
    seCrea: "Primera consulta exitosa",
    seElimina: "Solo por operación manual de demostración",
    consultan: "queries-service y la demostración con redis-cli",
  },
  {
    patron: "counter:queries:consultas:{YYYY-MM-DD}",
    componente: "queries-service",
    proposito: "Consultas exitosas del día",
    tipo: "string entero",
    ttl: "172800 s (48 h)",
    seCrea: "Primera consulta exitosa del día",
    seElimina: "Al vencer el TTL",
    consultan: "queries-service",
  },
  {
    patron: "counter:reports:generados",
    componente: "reports-service",
    proposito: "Total de reportes generados",
    tipo: "string entero",
    ttl: "Sin TTL: contador operativo",
    seCrea: "Primer reporte exitoso",
    seElimina: "Solo por operación manual de demostración",
    consultan: "reports-service",
  },
  {
    patron: "counter:reports:generados:{YYYY-MM-DD}",
    componente: "reports-service",
    proposito: "Reportes generados en el día",
    tipo: "string entero",
    ttl: "172800 s (48 h)",
    seCrea: "Primer reporte exitoso del día",
    seElimina: "Al vencer el TTL",
    consultan: "reports-service",
  },
  {
    patron: "cache:auth:contexto:{usuario_id}",
    componente: "middleware JWT de queries-service y reports-service",
    proposito: "Unidad de alcance del actor, para no consultar PostgreSQL en cada petición",
    tipo: "string JSON",
    ttl: "REDIS_TTL_CONTEXTO_SEC (60 s)",
    seCrea: "Primera petición autenticada del usuario en esa ventana",
    seElimina: "Al vencer el TTL",
    consultan: "queries-service y reports-service",
  },
];
