# data/

Esquema y semilla de PostgreSQL de la librería.

- `database/01_schema.sql` … `06_views.sql` — modelo
- `database/07_grants.sql` — permisos de `library_user`
- `database/soap_module.sql` — tablas SOAP (EG03)
- `database/docker-init.sh` — carga automática en Docker

La app Node lo usa con `npm run setup` desde `apps/web-monolito`.
Postgres de demostración: `127.0.0.1:5433`, usuario `library_user`, clave `666`.
