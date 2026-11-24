# queries-service

Consultas de solo lectura de Bienestar Nexum. El arranque normal es con Docker, desde `proyecto_final`:

```bash
docker compose up -d --build queries-service
```

Swagger: http://127.0.0.1:3010/api/docs

Salud: http://127.0.0.1:3010/health

Pruebas de esta carpeta:

```bash
npm test
```

La guía completa, los roles y las variables están en `Redis, Docker, consultas y pruebas/LEEME.md`.
