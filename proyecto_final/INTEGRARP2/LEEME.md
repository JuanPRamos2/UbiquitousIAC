# Aplicación integrada

Todo el segundo parcial se levanta desde esta carpeta.

```bash
cd INTEGRARP2
docker compose up -d
docker compose ps
```

| Qué | Dirección |
| --- | --- |
| Web | http://127.0.0.1:8000 |
| Auth | http://127.0.0.1:8101/api/v1/auth/login |
| Usuarios | http://127.0.0.1:8102 |
| Documentos | http://127.0.0.1:8103 |
| Notificaciones | http://127.0.0.1:8104 |
| Catálogos | http://127.0.0.1:3002/health |
| Proceso principal | http://127.0.0.1:3003/health |
| Consultas | http://127.0.0.1:3010/api/docs |
| Reportes | http://127.0.0.1:3020/api/docs |

El token sale de auth, campo `token_acceso`. Ese mismo token abre catálogos, consultas y reportes. Contraseña de demostración: `demo123`. Correo útil: `mariana.solis@nexum.com.mx`.
