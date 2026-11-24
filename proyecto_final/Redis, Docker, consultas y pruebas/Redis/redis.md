# Redis como componente común

## Por qué Redis

Nexum ya usaba Redis para la sesión, la revocación del JWT, la caché del agregado, el contador de login fallido y el bloqueo del cálculo de privacidad. En esta entrega Redis deja de ser un detalle del monolito y pasa a ser el almacén compartido de la red Docker. Consultas y reportes no abren otro Redis.

## Arquitectura

Un contenedor `redis` en la red `nexum`. Los servicios lo alcanzan por `redis:6379`. No hay contraseña en el entorno de demostración. La persistencia es AOF, volumen `redisdata`.

## Caché

```
petición
  → GET cache:{servicio}:{recurso}:{hash}
  → si existe: log CACHE HIT y se responde
  → si no: log CACHE MISS
  → se toma lock:cache:{servicio}:{recurso}:{hash} con SET NX EX
  → se consulta PostgreSQL o MongoDB
  → SET de la caché con TTL
  → se libera el lock
```

El hash incluye filtros, perfil y, cuando el resultado depende de la persona, el usuario. Así el líder no reutiliza la caché del administrador. `meta.cache` y `meta.clave_cache` dicen qué pasó. El log usa exactamente las cadenas `CACHE HIT` y `CACHE MISS`.

## TTL

| Patrón | Tipo | TTL | Se crea | Desaparece | Quién la consulta |
| --- | --- | --- | --- | --- | --- |
| `session:{jti}` | hash | 900 s, la vida del JWT | Login del Auth Service | Logout o vencimiento | Todos los servicios protegidos |
| `revoked:{jti}` | string | Segundos que le quedan al JWT | Logout | Al vencer | Todos los servicios protegidos |
| `contador:login_fallido:{usuario_id}` | string | 900 s | Primer login fallido | Acierto o vencimiento | Auth Service |
| `cache:agregado:{unidad}:{campania}` | string JSON | 300 s | Al calcular un agregado | TTL o invalidación del monolito | Proceso de agregados |
| `lock:calculo_agregado:{unidad}` | string | 10 s | Antes de calcular un agregado | Al terminar o al vencer | Proceso de agregados |
| `cache:{servicio}:{recurso}:{hash}` | string JSON | `CACHE_TTL_SEC` (60 s) | Tras un CACHE MISS | Al vencer | El servicio que la escribió |
| `lock:cache:{servicio}:{recurso}:{hash}` | string | `REDIS_TTL_LOCK_SEC` (10 s) | SET NX en un CACHE MISS | Al guardar la caché o al vencer | El servicio que llena esa caché |
| `ratelimit:{servicio}:{identidad}:{ventana}` | string | `RATE_LIMIT_WINDOW_SEC` (60 s) | Primera petición de la ventana | Al vencer la ventana | El servicio que limita |
| `counter:queries:consultas` | string | Sin TTL. Es un total, no un dato temporal | Primera consulta exitosa | Solo si se borra a mano en la demo | queries-service |
| `counter:queries:consultas:{fecha}` | string | 48 h | Primera consulta del día | Al vencer | queries-service |
| `counter:reports:generados` | string | Sin TTL | Primer reporte exitoso | Solo a mano | reports-service |
| `counter:reports:generados:{fecha}` | string | 48 h | Primer reporte del día | Al vencer | reports-service |
| `cache:auth:contexto:{usuario_id}` | string JSON | 60 s | Primera petición del usuario | Al vencer | queries-service y reports-service |

La fuente de esta tabla es `services/comun/src/claves-redis.js`. Una prueba unitaria exige que cada fila tenga patrón, TTL, componente y propósito.

## Sesiones

La sesión no se rediseñó. Sigue siendo `session:{jti}` porque ese es el contrato que ya escribe el login. Cambiarla a `session:{user}:{session}` rompería al resto del equipo. ESTO SE DEBE CONECTAR CON AUTH SERVICE: cuando exista, debe seguir escribiendo esa clave y `revoked:{jti}`.

## Tokens revocados

En cada ruta protegida el orden es: token presente, firma válida, no expirado, `revoked:{jti}` ausente, `session:{jti}` presente si `JWT_REQUIRE_SESSION` no está en false, y perfil autorizado. Si Redis no responde durante esa comprobación, la respuesta es 503. No se deja pasar el token "por si acaso".

## Rate limiting

`RATE_LIMIT_REQUESTS` y `RATE_LIMIT_WINDOW_SEC`. Al pasar el límite: HTTP 429, código `LIMITE_EXCEDIDO` y header `Retry-After`. Si Redis falla, el límite no se apaga: responde 503. El valor de demostración es 60 peticiones por minuto. La prueba de integración lo supera y obtiene 429.

## Contadores

Cada consulta exitosa hace `INCR counter:queries:consultas`. Cada reporte exitoso hace `INCR counter:reports:generados`. El contador del día sí expira. El total no, porque no es una clave temporal.

## Bloqueos distribuidos

Sí hay un caso real y sí está implementado: varias peticiones iguales pueden llegar juntas en un CACHE MISS y repetir la misma lectura. El lock `lock:cache:...` con expiración evita esa estampida. Si el proceso muere, el TTL suelta el lock.

No se agregó otro lock de negocio. El único cálculo concurrente que cambia estado y gasta presupuesto de privacidad ya tiene `lock:calculo_agregado:{unidad}` en el monolito. Consultas y reportes no ejecutan ese cálculo. Inventar un segundo bloqueo sobre una operación que estos servicios no hacen no aportaría una demostración honesta.

## Cómo lo usará el resto del equipo

Auth Service escribe `session:{jti}` y `revoked:{jti}`. Cualquier servicio nuevo puede copiar el middleware de `services/comun/src/jwt.js`. Para caché propia debe usar el prefijo `cache:{su-servicio}:` y ponerle TTL. No debe usar `KEYS` en código de producción. Para mirar claves en la demo local:

```bash
docker compose exec redis redis-cli
SCAN 0 MATCH cache:queries-service:* COUNT 20
GET cache:queries-service:campanias:<hash que devolvió meta.clave_cache>
TTL <esa clave>
GET counter:queries:consultas
GET counter:reports:generados
TTL counter:queries:consultas
GET revoked:<jti>
TTL session:<jti>
```

`TTL` de un contador total responde `-1` (existe y no expira). `TTL` de una caché responde los segundos que le quedan.

## Beneficios

La segunda lectura no vuelve a PostgreSQL durante el TTL. El límite de peticiones es el mismo para todos los contenedores. La revocación del logout se ve enseguida en consultas y reportes, sin otro mecanismo de sesión.
