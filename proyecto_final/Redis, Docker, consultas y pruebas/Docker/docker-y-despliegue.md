# Docker

## Arquitectura de contenedores

Red `nexum`. Cada proceso escucha dentro de su contenedor y se llama por el nombre del servicio.

```
api (alias web)          :3000   host API_HOST_PORT (3001 en este entorno)
queries-service          :3000   host 3010
reports-service          :3000   host 3020
postgres (alias postgresql) :5432 host 5433
mongo (alias mongodb)    :27017  host 27017
redis                    :6379   host 6379
```

Comprobado desde `queries-service`: `http://reports-service:3000/health` responde 200 y `http://api:3000/api/salud` es alcanzable. PostgreSQL, MongoDB y Redis responden en el health de cada microservicio (`dependencies` en `up`).

## Dockerfiles

- `Dockerfile` del monolito, sin cambio de comportamiento. Sigue sirviendo la web.
- `services/queries-service/Dockerfile`
- `services/reports-service/Dockerfile`

Las imágenes de los microservicios parten de `node:22-bookworm-slim`, instalan dependencias con `npm ci`, copian el código, cambian al usuario `node` y no incluyen `.env`.

## Docker Compose

`docker-compose.yml` conserva PostgreSQL, MongoDB, Redis y el API. Agrega los dos microservicios, la red `nexum` y alias DNS. Los servicios que el equipo todavía no ha extraído quedan descritos en comentarios, no como contenedores vacíos que finjan estar terminados:

- auth-service, users-service, catalog-service, main-process-service, documents-service y notifications-service.

Hoy esas responsabilidades siguen en `api`. El DNS `web` apunta a ese contenedor. ESTO SE DEBE CONECTAR CON AUTH SERVICE en `http://api:3000/api/auth/login` hasta que el contenedor propio exista. Entonces se sustituye el alias, no el contrato de Redis ni el JWT.

## Red, volúmenes y puertos

Red bridge `nexum`. Volúmenes `pgdata`, `mongodata` y `redisdata`. El SQL inicial es `bienestar_nexum_v2.sql`. Los microservicios no tienen volumen: no guardan estado en disco.

`depends_on` espera a que Postgres, Mongo y Redis pasen el healthcheck. Cada microservicio tiene healthcheck sobre `GET /health`.

## Variables

Compose inyecta las variables en cada contenedor. No usa `env_file` para la aplicación porque el `.env` del host tiene `localhost`, y eso rompería la red interna. El `.env` solo interpola puertos y el secreto compartido.

## Cómo operarlo

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs queries-service
docker compose logs reports-service
docker compose down
```

Para reconstruir solo un servicio:

```bash
docker compose up -d --build queries-service reports-service
```

Para ver el estado:

```bash
docker compose ps
curl -s http://127.0.0.1:3010/health
curl -s http://127.0.0.1:3020/health
```

`docker compose down` detiene y borra contenedores. `docker compose down -v` además borra las bases. No hace falta para una demo normal.
