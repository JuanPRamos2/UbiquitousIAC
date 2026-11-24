# Reports Service

## Decisión

Se implementó Reports Service y no Algorithms Service. El algoritmo de privacidad diferencial ya está en PostgreSQL (`agregado.fn_calcular_agregado_protegido`) y lo dispara el proceso de agregados del monolito. Volver a ejecutarlo desde reportes gastaría el presupuesto de épsilon y duplicaría una regla de negocio que no corresponde a esta parte. Un reporte, en este dominio, es una lectura agrupada: totales, distribuciones y series para gráficas.

## 1. Nombre

reports-service.

## 2. Propósito

Entregar totales y series que la web puede pintar con Highcharts, a partir de campañas, reglas, fuentes, intervenciones, bitácora, publicación protegida y solicitudes de apoyo.

## 3. Responsabilidad

Agregar. No modifica parámetros de privacidad, no propone intervenciones y no lee respuestas crudas.

## 4. Justificación

El tablero del líder y del especialista ya está pensado como información de grupo. El reporte conserva esa regla: si el grupo no llega al umbral k, el punto de la serie va vacío y no se envía el n exacto.

## 5. Relación con los requerimientos

Cubre el microservicio de reportes, las series para Highcharts, JSON, XML, XSD, JWT, roles, Redis, las dos bases, Swagger y pruebas.

## 6. Arquitectura interna

La misma capa que consultas: rutas, validación, servicio, repositorio y SQL. Comparte `services/comun`.

## 7. Tecnología

Node.js 22 y Express, igual que el resto del proyecto.

## 8. Dependencias

PostgreSQL, MongoDB y Redis. El JWT lo emite hoy el monolito.

## 9. Endpoints

Prefijo `/api/v1/reports`.

| Método | Ruta | Qué devuelve | Quién |
| --- | --- | --- | --- |
| GET | `/resumen` | Totales de campañas, unidades, intervenciones y resultados | Líder, especialista, auditor, administrador |
| GET | `/campanias-por-estado` | Barras ABIERTA / CERRADA | Cualquier perfil autenticado |
| GET | `/intervenciones-por-estado` | Planes por estado. Vacío si no hay planes | Perfiles organizacionales |
| GET | `/reglas-por-nivel` | Reglas activas por nivel | Perfiles organizacionales |
| GET | `/fuentes` | Autorizadas frente a prohibidas | Cualquier perfil autenticado |
| GET | `/tendencia` | Participación suficiente y valor protegido | Perfiles organizacionales |
| POST | `/tendencia` | Lo mismo, con filtros JSON o XML | Perfiles organizacionales |
| GET | `/auditoria-por-accion` | Conteos de la bitácora | Auditor y administrador |
| GET | `/auditoria-por-periodo` | Eventos por día | Auditor y administrador |
| GET | `/publicacion` | Estados ya guardados en `resultado_protegido` | Perfiles organizacionales |
| GET | `/solicitudes-apoyo` | Agregación de MongoDB por estado | Auditor y administrador |
| GET | `/observabilidad` | `counter:reports:generados` | Administrador |

La forma de la gráfica es siempre:

```json
{
  "categories": ["ABIERTA", "CERRADA"],
  "series": [{ "name": "Campañas", "data": [1, 3] }]
}
```

Con los datos que haya en PostgreSQL. El servicio cuenta las campañas por estado. Con la carga actual se ven 1 abierta y 3 cerradas. Si se agrega o cambia una campaña, la respuesta cambia. No es un arreglo fijo en el código: es `GROUP BY estado`.

## 10. Requests

GET con `desde`, `hasta`, `unidad_organizacional_id` y `dimension_id` cuando aplica. POST `/tendencia` acepta JSON y XML. El XML se valida con `reporte-tendencia.xsd`. Si `desde` es posterior a `hasta`, la respuesta es 422.

## 11. Responses

El mismo sobre `success`, `message`, `data` y `meta` de consultas. En XML, cada categoría es `<category>` y cada punto es `<point>`. Un punto vacío significa null para Highcharts y representa un grupo bajo el umbral k. El esquema está en `reporte-highcharts.xsd`.

## 12. JWT

El mismo middleware. ESTO SE DEBE CONECTAR CON AUTH SERVICE sin cambiar el código de las rutas: el token, `session:{jti}` y `revoked:{jti}` son el contrato.

## 13. Roles

El colaborador puede ver campañas por estado y la gráfica de fuentes, que son catálogo. No puede ver el resumen organizacional ni la tendencia: eso responde 403. El líder que pide `UO-LOG-TURNO-A` también recibe 403, porque su alcance es `UO-CC-TURNO-B`.

## 14. Persistencia

PostgreSQL para todos los conteos de negocio. MongoDB para agrupar `solicitudes_apoyo` por estado. Si la colección está vacía, la serie queda vacía y la nota lo dice. No se inventan solicitudes.

## 15. Redis

Caché `cache:reports-service:{recurso}:{hash}`, TTL 60 s por defecto. Contador `counter:reports:generados` y el diario con TTL de 48 h. Rate limit y lock de estampida con el mismo mecanismo de consultas.

## 16. Integración

`/publicacion` y la serie "Valor protegido" leen lo que el proceso principal ya haya guardado. Si esa tabla sigue vacía, la serie va en null y la nota explica que todavía no hay publicación. Eso queda pendiente del integrante del proceso principal; no se rellena con números falsos.

## 17. Docker

`services/reports-service/Dockerfile`. Misma base ligera y usuario `node`.

## 18. Puerto

3000 en la red Docker. 3020 en el host (`REPORTS_HOST_PORT`).

## 19. Variables de entorno

Las mismas de consultas, con `SERVICE_NAME=reports-service`.

## 20. Evidencias

[evidencias de pruebas](../Pruebas/evidencias-de-pruebas.md). La página `web/consultas-reportes.html` entra con el login del monolito y dibuja la serie real.

## 21. Pruebas

`services/reports-service/tests/reportes.test.js` comprueba que un grupo con n menor que k no publica el tamaño y que el líder no cambia de unidad. La integración lo confirma contra PostgreSQL.
