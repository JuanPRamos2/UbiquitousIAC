# Auditoría final del esta parte

| Requisito | Estado | Evidencia | Archivo o endpoint | Pendiente |
| --- | --- | --- | --- | --- |
| Queries Service funcional | COMPLETO | integración y curl 200 | `/api/v1/queries/campanias` | — |
| Reports Service funcional | COMPLETO | serie `[1, 3]` y gráfica Highcharts | `/api/v1/reports/campanias-por-estado` | El valor protegido numérico espera filas del proceso principal |
| Algorithms Service | NO APLICA | Decisión documentada | `Reportes/servicio-de-reportes.md` | — |
| Redis funcional | COMPLETO | health redis up | contenedor redis | — |
| Caché real | COMPLETO | MISS y luego HIT en el mismo filtro | `meta.cache` | — |
| TTL | COMPLETO | `TTL` positivo en la clave de caché | `CACHE_TTL_SEC` | — |
| Contadores | COMPLETO | `GET counter:queries:consultas` | observabilidad | — |
| Rate limiting | COMPLETO | integración obtuvo 429 | `RATE_LIMIT_REQUESTS` | — |
| Sesión y revocación | COMPLETO en los consumidores | token del login real aceptado; revocado rechazado | `session:{jti}`, `revoked:{jti}` | El emisor sigue en el monolito |
| Distributed locks | COMPLETO | lock de estampida; lock de agregado ya existente | `Redis/redis.md` | — |
| Dockerfiles | COMPLETO | imágenes construidas | `services/*/Dockerfile` | — |
| Docker Compose general | COMPLETO para lo existente | `docker compose ps` healthy | `docker-compose.yml` | Contenedores de los otros integrantes |
| Networks | COMPLETO | `reports-service` y `api` resueltos desde consultas | red `nexum` | — |
| Volúmenes | COMPLETO | pgdata, mongodata, redisdata | compose | — |
| Variables de entorno | COMPLETO | `.env.example` sin secretos reales | `.env.example` | — |
| Healthchecks | COMPLETO | status healthy | `GET /health` | — |
| Comunicación entre contenedores | COMPLETO | health de dependencias y HTTP interno | DNS de Compose | — |
| JSON | COMPLETO | sobre success/data | respuestas 200 | — |
| XML | COMPLETO | Content-Type application/xml | Accept y POST | — |
| XSD | COMPLETO | válido pasa, inválido falla | `services/comun/xsd` | — |
| JWT y roles | COMPLETO | 401 y 403 probados | middleware común | Auth Service como contenedor propio |
| Swagger | COMPLETO | `/api/docs` HTTP 200 en ambos | Try it out | — |
| Logging | COMPLETO | CACHE HIT/MISS sin JWT completo | logs de contenedor | — |
| Errores | COMPLETO | 400, 401, 403, 404, 422, 429, 500, 503 | `http.js` | 409 no tiene un caso de negocio en lectura |
| Pruebas unitarias | COMPLETO | 16 passed | `npm run test:micro` | — |
| Pruebas de integración | COMPLETO para lo disponible | 3 passed | `tests/integracion/flujos.test.js` | El flujo no puede entrar a un auth-service que no existe |
| Evidencias request/response | COMPLETO como guion y respuestas reales | `Pruebas/evidencias-de-pruebas.md` | capturas listadas para el documento | Las capturas de pantalla las toma quien presenta |
| Evidencias Redis | COMPLETO | comandos GET y TTL | `Redis/redis.md` | — |
| Evidencias Docker | COMPLETO | ps healthy | `DOCKER.md` | — |
| Documentación técnica | COMPLETO | esta carpeta | `Redis, Docker, consultas y pruebas` | — |
| Matriz de trazabilidad | COMPLETO | `MATRIZ.md` | — | — |
| Arquitectura | COMPLETO | diagrama en `ARQUITECTURA.md` y anexo en `docs/arquitectura.md` | — | — |
| Conclusiones | COMPLETO | `CONCLUSIONES.md` | — | — |
| Guion presencial | COMPLETO | `GUIONES.md` | — | — |
| Guion de YouTube | COMPLETO | `GUIONES.md` | — | — |

No se marca como completo el contenedor de Auth Service ni la serie de valores protegidos cuando la tabla de publicación está vacía. Esas dos dependencias están escritas como pendientes de integración.
