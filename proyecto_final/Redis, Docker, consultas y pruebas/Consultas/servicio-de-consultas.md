# Queries Service

## 1. Nombre

queries-service.

## 2. Propósito

Ofrecer consultas de solo lectura sobre el dominio que ya existe en Bienestar Nexum: campañas, unidades, instrumentos, fuentes de datos, intervenciones organizacionales, bitácora, resultados protegidos, presupuesto de privacidad, solicitudes de apoyo y la participación del propio colaborador.

## 3. Responsabilidad

Responder preguntas. No crea campañas, no guarda respuestas y no recalcula el agregado con ruido de Laplace. Esa escritura sigue en el monolito, que hoy concentra el proceso principal hasta que el equipo lo separe.

## 4. Justificación

El primer parcial ya dejó las vistas que cada perfil puede leer: `agregado.v_tablero_unidad`, `agregado.v_estado_presupuesto`, `auditoria.v_tablero_auditoria` y `portal.v_participacion_propia`. El servicio de consultas las usa. No existe un permiso de lectura de respuestas individuales y este servicio tampoco lo crea.

## 5. Relación con los requerimientos

Cubre el microservicio de consultas, la paginación, los filtros, JSON, XML, XSD, JWT, roles, Redis, PostgreSQL, MongoDB, Swagger, salud y pruebas.

## 6. Arquitectura interna

```
src/rutas/consultas.rutas.js
  → validacion.js
  → servicios/consultas.servicio.js
  → repositorios/consultas.repositorio.js
  → sql/consultas.sql.js
```

La autenticación, la caché, el límite de peticiones, el XML y los errores viven en `services/comun`, para que reports-service use el mismo contrato.

## 7. Tecnología

Node.js 22, Express, `pg`, `mongodb`, `ioredis`, `jsonwebtoken`, `fast-xml-parser`, Swagger UI. Es el mismo lenguaje del monolito.

## 8. Dependencias

PostgreSQL `bienestar_nexum`, MongoDB `bienestar_nexum` (colección `solicitudes_apoyo`), Redis y el JWT que hoy firma el monolito.

## 9. Endpoints

Prefijo `/api/v1/queries`. Todos exigen `Authorization: Bearer`, salvo `/health`, `/api/docs` y `/api/v1/xsd`.

| Método | Ruta | Quién |
| --- | --- | --- |
| GET | `/campanias` | Cualquier perfil autenticado |
| POST | `/campanias/buscar` | Cualquier perfil autenticado. JSON o XML |
| GET | `/campanias/:campaniaId` | Cualquier perfil autenticado |
| GET | `/unidades` | Cualquier perfil autenticado |
| GET | `/unidades/:unidadId` | Cualquier perfil autenticado |
| GET | `/instrumentos` | Cualquier perfil autenticado |
| GET | `/fuentes` | Cualquier perfil autenticado |
| GET | `/intervenciones` | Líder (su unidad), especialista, auditor, administrador |
| GET | `/intervenciones/:intervencionId` | Los mismos. 403 si el líder pide otra unidad |
| GET | `/auditoria` | Auditor y administrador |
| POST | `/auditoria/buscar` | Auditor y administrador. JSON o XML |
| GET | `/resultados-protegidos` | Perfiles organizacionales. El líder solo ve su unidad |
| GET | `/presupuesto` | Perfiles organizacionales. El líder solo ve su unidad |
| GET | `/solicitudes-apoyo` | Auditor y administrador. Sin seudónimo |
| GET | `/mi-participacion` | Colaborador, solo su fila |
| GET | `/observabilidad` | Administrador. Lee el contador, no hace `KEYS` |

Parámetros comunes: `page`, `limit` (1 a 100), `search`, `sort`, `order`.

## 10. Requests

GET usa query string. POST acepta `Content-Type: application/json` o `application/xml`. El XML de campañas se valida contra `busqueda-campanias.xsd`. El de auditoría, contra `busqueda-auditoria.xsd`. Un XML bien formado que no cumple el esquema responde 422. Un XML ilegible responde 400.

## 11. Responses

JSON:

```json
{
  "success": true,
  "message": "Campañas consultadas",
  "data": { "campanias": [] },
  "pagination": { "page": 1, "limit": 20, "total": 4, "totalPages": 1 },
  "meta": { "cache": "MISS", "servicio": "queries-service", "clave_cache": "cache:queries-service:campanias:..." }
}
```

El error no incluye el stack:

```json
{
  "success": false,
  "error": { "code": "NO_ENCONTRADO", "message": "La campaña no existe", "details": {} }
}
```

`/health` usa el formato pedido para el chequeo de dependencias y no este sobre. Así lo consume Docker sin envolverlo.

## 12. JWT

ESTO SE DEBE CONECTAR CON AUTH SERVICE. Hoy el emisor es `POST http://api:3000/api/auth/login`. El middleware comprueba firma HS256, expiración, claims `sub`, `perfil` y `jti`, la clave `revoked:{jti}` y la sesión `session:{jti}`. Si más adelante Auth Service publica RS256, se configuran `JWT_ALGORITHM` y `JWT_PUBLIC_KEY`. `JWT_ISSUER` y `JWT_AUDIENCE` solo se exigen cuando tienen valor, porque el token actual no los trae.

## 13. Roles

Se reutilizan los cinco perfiles de `usuarios.perfil`: COLABORADOR, LIDER, ESPECIALISTA, AUDITOR y ADMINISTRADOR. El líder queda acotado a `unidad_alcance_id`, que en los datos de prueba es `UO-CC-TURNO-B` para Lucía.

## 14. Persistencia

PostgreSQL para catálogos, intervenciones, bitácora y vistas protegidas. MongoDB solo para `solicitudes_apoyo`, y la proyección omite `seudonimo_id`. Las consultas SQL van parametrizadas. El ordenamiento sale de una lista blanca.

## 15. Redis

Caché `cache:queries-service:{recurso}:{hash}` con TTL `CACHE_TTL_SEC` (60 s). En el log aparece `CACHE MISS` y después `CACHE HIT`. Contador `counter:queries:consultas`. Límite `ratelimit:queries-service:{usuario}:{ventana}`. Contexto `cache:auth:contexto:{usuario_id}`. Lock de estampida `lock:cache:queries-service:{recurso}:{hash}`.

## 16. Integración

Lee la base que ya alimenta el monolito. No llama al cálculo de privacidad diferencial, porque cada llamada gasta épsilon. Cuando el proceso principal publique filas en `agregado.resultado_protegido`, este servicio las muestra sin cambiar de contrato.

## 17. Docker

Imagen `node:22-bookworm-slim`, usuario `node`, sin secretos en la imagen. Dockerfile: `services/queries-service/Dockerfile`.

## 18. Puerto

3000 dentro de la red. En el host, 3010 (`QUERIES_HOST_PORT`).

## 19. Variables de entorno

Están en `.env.example`: `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_PUBLIC_KEY`, `JWT_REQUIRE_SESSION`, `POSTGRES_*`, `MONGO_URL`, `MONGO_DB`, `REDIS_URL`, `CACHE_TTL_SEC`, `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SEC`, `REDIS_TTL_LOCK_SEC`, `CORS_ORIGINS`.

## 20. Evidencias

[evidencias de pruebas](../Pruebas/evidencias-de-pruebas.md).

## 21. Pruebas

`services/queries-service/tests/consultas.test.js` cubre validación, SQL parametrizado, 404 y el 403 del líder. La integración cubre el flujo completo contra Docker.
