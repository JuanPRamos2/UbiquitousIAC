# Arquitectura políglota

PostgreSQL (negocio y catálogos) · MongoDB (encuestas y bitácora) · Redis (sesión, caché, locks).

La app Node orquesta las tres. No hay JOIN cruzado: se validan IDs en Postgres
y se persisten los mismos IDs en Mongo.

`consentimiento.seudonimo` es el único vínculo `empleado_id` ↔ `seudonimo_id`.
Las respuestas nunca guardan `empleado_id`. El documento Mongo incluye
`version_consentimiento` (decisión D-02).

La bitácora vive en MongoDB. Los códigos `accion`, `recurso` y `resultado`
se validan contra `auditoria.tipo_accion`, `auditoria.tipo_recurso` y
`auditoria.resultado_auditoria`.

Detalle de cumplimiento: [AUDITORIA.md](./AUDITORIA.md).

## Segundo parcial — consultas, reportes y Redis

El monolito sigue siendo la aplicación web y, mientras el equipo no extraiga los demás servicios, también la autenticación. Sobre esa base se agregan dos servicios de solo lectura:

```
web (api:3000)
  → JWT emitido por /api/auth/login
  → queries-service:3000 y reports-service:3000
  → Redis (sesión, revocación, caché, rate limit, contadores, locks)
  → PostgreSQL y MongoDB
```

La documentación de esa parte está en [Redis, Docker, consultas y pruebas](../Redis,%20Docker,%20consultas%20y%20pruebas/LEEME.md).
Los contenedores se publican en el host en los puertos 3010 (consultas) y 3020 (reportes).
La web sigue en `API_HOST_PORT` (en este entorno, 3001).
