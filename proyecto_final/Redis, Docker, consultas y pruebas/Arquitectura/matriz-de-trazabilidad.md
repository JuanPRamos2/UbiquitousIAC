# Matriz de trazabilidad — esta parte

| Requerimiento | Componente | Implementación | Endpoint o archivo | Prueba | Evidencia | Estado |
| --- | --- | --- | --- | --- | --- | --- |
| Servicio de consultas | queries-service | Lecturas del dominio Nexum, sin respuestas individuales | `/api/v1/queries/*` | `consultas.test.js`, integración | Pruebas/evidencias-de-pruebas.md | COMPLETO |
| Paginación, orden y filtros | queries-service | `page`, `limit`, `sort`, `order`, `search` | `services/comun/src/paginacion.js` | prueba de page 0 y sort inválido | 400 documentado | COMPLETO |
| Servicio de reportes | reports-service | Series Highcharts desde PostgreSQL y MongoDB | `/api/v1/reports/*` | `reportes.test.js`, integración | Gráfica en `consultas-reportes.html` | COMPLETO |
| Algorithms Service | — | No se creó: el algoritmo de Laplace ya vive en PostgreSQL y lo ejecuta el proceso principal | `Reportes/servicio-de-reportes.md` | — | Decisión escrita | COMPLETO como decisión |
| Redis caché con TTL | Redis compartido | CACHE HIT / CACHE MISS y `SET EX` | `services/comun/src/cache.js` | prueba unitaria de hit y miss; integración | `meta.cache` y `TTL` | COMPLETO |
| Contadores | Redis | `INCR counter:queries:consultas` y `counter:reports:generados` | `services/comun/src/cache.js` | prueba del TTL diario | `GET` en redis-cli | COMPLETO |
| Rate limiting | Redis | 429 configurable por entorno | `services/comun/src/rate-limit.js` | unitaria 429 y 503; integración 429 | header Retry-After | COMPLETO |
| JWT revocado y sesión | Redis + middleware | `revoked:{jti}` y `session:{jti}` | `services/comun/src/jwt.js` | unitaria e integración | logout / SET revoked | COMPLETO en contrato; el emisor sigue siendo el monolito |
| Bloqueo distribuido | Redis | Lock de estampida de caché. El lock del agregado ya existía en el monolito | `lock:cache:*` y `lock:calculo_agregado:*` | el flujo de caché toma y suelta el lock | Redis/redis.md | COMPLETO |
| Docker de los servicios propios | queries y reports | Dockerfile por servicio | `services/*/Dockerfile` | `docker compose ps` healthy | DOCKER.md | COMPLETO |
| Docker del sistema | Compose | api, postgres, mongo, redis, queries, reports, red y healthchecks | `docker-compose.yml` | `docker compose config`, build, up, ps | seis contenedores healthy | COMPLETO para lo que existe |
| Servicios de otros integrantes en contenedor propio | auth, users, catalog, main-process, documents, notifications | Siguen dentro de `api`. El Compose documenta el nombre DNS futuro | comentarios de `docker-compose.yml` | no se simulan como contenedores vacíos | DOCKER.md | PENDIENTE DE INTEGRACIÓN |
| JSON | ambos servicios | Sobre `success` / `error` | `services/comun/src/http.js` | integración | respuesta de campañas | COMPLETO |
| XML de salida | ambos servicios | `Accept: application/xml` y serialización con XMLBuilder | `services/comun/src/xml.js` | XSD unitario e integración | Content-Type application/xml | COMPLETO |
| XML de entrada | POST de búsqueda y de tendencia | `Content-Type: application/xml` validado contra XSD | rutas POST | integración 200 y 422 | Pruebas/evidencias-de-pruebas.md | COMPLETO |
| XSD | contratos de consultas y reportes | Seis esquemas en `services/comun/xsd` | `GET /api/v1/xsd/:nombre` | XML válido pasa; inválido falla | prueba unitaria | COMPLETO |
| Swagger ejecutable | ambos servicios | OpenAPI 3 y Swagger UI | `/api/docs` | HTTP 200 de `/api/docs` y `/api/docs.json` | Try it out | COMPLETO |
| Pruebas unitarias | comun, queries, reports | 16 pruebas | `npm run test:micro` | 16 passed | salida de npm | COMPLETO |
| Pruebas de integración | sistema disponible | Login no incluido como emisor nuevo; el token del monolito y Redis sí | `tests/integracion/flujos.test.js` | 3 passed | flujos 200, 400, 401, 403, 404, 422, 429, HIT, XML, Mongo | COMPLETO para los servicios disponibles |
| Flujo login de un Auth Service futuro | auth-service | El monolito ya emite el JWT compatible | `POST /api/auth/login` | curl con el token real contra consultas | token de Mariana aceptado | PENDIENTE DE INTEGRACIÓN del contenedor propio |
| Healthchecks | ambos servicios y Compose | aplicación, Postgres, Mongo y Redis | `GET /health` | contenedores healthy | curl /health | COMPLETO |
| Valores protegidos publicados | reports `/publicacion` y serie de tendencia | Lee `resultado_protegido` si el proceso principal ya escribió | `/api/v1/reports/publicacion` | la serie queda vacía o en null si no hay filas | nota del endpoint | PENDIENTE DE INTEGRACIÓN con el proceso que publica |
| Android y escritorio | consumidores futuros | JSON y XML documentados. No hay aplicación cliente en esta entrega | Swagger y XSD | — | enunciado del parcial | Fuera de esta entrega |
