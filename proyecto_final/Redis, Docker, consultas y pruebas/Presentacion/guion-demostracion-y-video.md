# Guion de demostración

Duración orientativa: 6 a 8 minutos. Sustituye 3001 por 3000 si ese es tu `API_HOST_PORT`.

1. En la carpeta `proyecto_final`, ejecuta `docker compose ps`. Muestra los seis contenedores en healthy: api, queries-service, reports-service, postgres, mongo y redis.
2. Di que la web sigue siendo el monolito y que consultas y reportes son contenedores distintos en la red `nexum`.
3. Abre http://127.0.0.1:3010/api/docs. Authorize con un token del login. Ejecuta GET `/api/v1/queries/campanias?estado=ABIERTA&limit=2`.
4. Señala `meta.cache: MISS` la primera vez. En otra terminal: `docker compose logs queries-service` y muestra la línea `CACHE MISS`.
5. Repite Try it out. Ahora `meta.cache` es `HIT` y el log dice `CACHE HIT`.
6. Copia `meta.clave_cache`. En Redis: `docker compose exec redis redis-cli` y luego `GET` de esa clave y `TTL`. El TTL es positivo.
7. Repite la llamada con el header `Accept: application/xml`. Muestra `Content-Type: application/xml` y el elemento `<campania>`.
8. Abre `services/comun/xsd/consulta-campanias.xsd`. Di que la prueba unitaria acepta el XML válido y rechaza un `<estado>` que no está en la enumeración.
9. Abre http://127.0.0.1:3020/api/docs y ejecuta GET `/api/v1/reports/campanias-por-estado`. Muestra `categories` ABIERTA y CERRADA y `data` 1 y 3.
10. Abre http://127.0.0.1:3001/consultas-reportes.html, entra como Mariana y muestra la misma gráfica en Highcharts.
11. Quita el token y llama campañas. Muestra 401 `SIN_TOKEN`.
12. Entra como Ana y llama `/api/v1/queries/auditoria`. Muestra 403.
13. Llama `/api/v1/queries/campanias/CAMP-NO-EXISTE` y muestra 404. Llama con `page=0` y muestra 400.
14. Repite una ruta más de 60 veces, o baja `RATE_LIMIT_REQUESTS` a 3, reconstruye y haz cuatro llamadas. Muestra 429.
15. En Redis: `GET counter:queries:consultas` y `GET counter:reports:generados`.
16. Cierra sesión en la web y reutiliza el token viejo. Muestra 401 `TOKEN_REVOCADO`. En Redis, `GET revoked:{jti}`.
17. Ejecuta `npm run test:micro` y `INTEGRACION=1 npm run test:integracion`.

# Guion para el video

Esta parte debe durar unos 3 minutos. Habla en primera persona y enseña la pantalla que se indica. No leas el código.

1. Pantalla: terminal en `proyecto_final`. Di: "Mi parte son las consultas, los reportes, Redis y el despliegue con Docker". Ejecuta `docker compose ps`. Di: "Cada servicio está en su contenedor y se hablan por el nombre de la red, no por localhost".
2. Pantalla: http://127.0.0.1:3010/health. Di: "El health revisa la aplicación, PostgreSQL, MongoDB y Redis".
3. Pantalla: Swagger de consultas. Ejecuta la campaña abierta. Di: "La primera vez es CACHE MISS: no estaba en Redis, así que leyó PostgreSQL".
4. Repite. Di: "La segunda es CACHE HIT. Redis respondió y la clave tiene TTL". Muestra `TTL` en redis-cli.
5. Cambia Accept a XML. Di: "El mismo recurso responde XML si el cliente lo pide. El XSD está publicado en /api/v1/xsd".
6. Pantalla: Swagger de reportes, campañas por estado. Di: "El reporte no trae números fijos. Agrupa las campañas reales: una abierta y tres cerradas, listo para Highcharts".
7. Pantalla: `consultas-reportes.html` con la gráfica. Di: "La web entra con el JWT del login y consume el reporte".
8. Pantalla: una llamada sin token y otra con Ana a auditoría. Di: "Sin token es 401. Sin permiso es 403. Si me paso del límite, Redis responde 429".
9. Pantalla: `npm run test:integracion` en verde. Di: "Las pruebas de integración cruzan el token, Redis, el servicio y la base".
10. Cierra: "Auth Service todavía puede vivir en el monolito. Cuando lo separen, el contrato ya está: el mismo JWT y las claves session y revoked en Redis".
