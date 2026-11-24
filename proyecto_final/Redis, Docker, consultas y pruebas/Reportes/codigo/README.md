# reports-service

Reportes agregados de Bienestar Nexum, con series listas para Highcharts. No recalcula la privacidad diferencial: lee lo que ya está en PostgreSQL y MongoDB.

```bash
docker compose up -d --build reports-service
```

Swagger: http://127.0.0.1:3020/api/docs

Salud: http://127.0.0.1:3020/health

La gráfica de la web está en http://127.0.0.1:3001/consultas-reportes.html cuando la web se publica en 3001.

```bash
npm test
```

Detalle en `Redis, Docker, consultas y pruebas/Reportes/servicio-de-reportes.md`.
