# Bienestar Nexum

Monolito web del primer parcial: bienestar laboral y prevención de burnout
(EQUIPO 03). PostgreSQL + MongoDB + Redis. El único pivote entre identidad real
y operativa es `consentimiento.seudonimo`. No hay JOIN entre MongoDB y PostgreSQL.

Informe de auditoría: [docs/AUDITORIA.md](docs/AUDITORIA.md).

En el portafolio del curso esta carpeta es `UbiquitousIAC/proyecto_final/`.
`index.html` abre el reporte del sitio; `web/index.html` es la interfaz Nexum.
Ubiquitous no ejecuta Node: el API se corre en local con Docker (`npm start` / Compose).

## Arranque con contenedores (Debian)

En Arch o Debian, Docker Compose v2 necesita el plugin Buildx:

```bash
# Arch
sudo pacman -S docker-buildx

# Debian / Ubuntu
sudo apt install docker-buildx-plugin
```

PostgreSQL del host suele ocupar el puerto 5432. Compose publica el contenedor
en **5433**. La app se sirve en **3000**.

```bash
cp -n .env.example .env
sudo docker compose down
sudo docker compose up --build -d
sudo docker compose ps
```

`-d` corre en segundo plano. No te quedes viendo logs JSON de Mongo: eso no es la app.

Abre [http://127.0.0.1:3000](http://127.0.0.1:3000). El encabezado debe mostrar
`PostgreSQL · MongoDB · Redis conectados`.

Para ver solo la API:

```bash
sudo docker compose logs -f api
```

### Puerto ya en uso (`address already in use`)

`systemctl stop postgresql` solo libera **5432**. Si el error menciona `0.0.0.0:3000`, hay otro proceso (Node, otro Compose, o un `iac-api` viejo).

```bash
cd proyecto_final
sudo ss -tlnp | grep -E ':3000|:5432|:5433|:27017|:6379'
sudo docker compose down
sudo fuser -k 3000/tcp || true
sudo docker compose up --build
```

Si 3000 sigue ocupado, en `.env` pon `API_HOST_PORT=3001` y abre http://127.0.0.1:3001. Lo mismo existe para `MONGO_HOST_PORT` y `REDIS_HOST_PORT`.

Si el volumen de Postgres ya existía **antes** de añadir
`db/postgres/03_recurso_usuario.sql`, recréalo con `down -v` o el recurso
`USUARIO` no estará en el catálogo de auditoría.

| Correo | Perfil | Clave |
| --- | --- | --- |
| ana.perez@empresa.com | COLAB | demo123 |
| lucia.hernandez@empresa.com | LIDER_TURNO | demo123 |
| roberto.garcia@empresa.com | AUDITOR | demo123 |
| carlos.ramirez@empresa.com | ADMIN_SISTEMA | demo123 |

Las contraseñas se verifican en PostgreSQL con `pgcrypto` (`crypt` + Blowfish).

## API

| Método | Ruta | Quién |
| --- | --- | --- |
| GET | `/api/salud` | público |
| POST | `/api/auth/login` | público |
| POST | `/api/auth/logout` | sesión |
| GET | `/api/auth/me` | sesión |
| GET | `/api/catalogos/unidades` | autenticado |
| GET | `/api/catalogos/campanias` | autenticado |
| GET | `/api/catalogos/instrumentos` | autenticado |
| GET | `/api/encuestas/estado` | COLAB |
| POST | `/api/encuestas/respuestas` | COLAB |
| GET | `/api/agregados/parametros/k` | LIDER / AUDITOR / ADMIN |
| GET | `/api/agregados/:unidad/:campania` | LIDER / AUDITOR / ADMIN |
| PATCH | `/api/agregados/parametros/k` | ADMIN |
| GET | `/api/auditoria` | AUDITOR / ADMIN |
| GET | `/api/auditoria/consentimientos/:seudonimoId` | AUDITOR / ADMIN |

POST encuesta:

1. Valida `seudonimo_id`, campaña, consentimiento y reactivos en PostgreSQL.
2. Inserta en MongoDB `respuestas_encuesta` (sin `empleado_id`, con `version_consentimiento`).
3. Invalida `cache:agregado:{unidad}:{campania}`.
4. Escribe `CREACION_RESPUESTA` en `bitacora_auditoria`.

Si hay menos de **k** respuestas (k=5), el agregado responde `GRUPO_INSUFICIENTE`
sin totales ni promedios.

## Redis

| Clave | Tipo | TTL |
| --- | --- | --- |
| `session:{jti}` | Hash | 15 min |
| `revoked:{jti}` | String | resto de vida del JWT |
| `cache:agregado:{unidad}:{campania}` | String JSON | 5 min |
| `contador:login_fallido:{usuario_id}` | String int | 15 min |
| `lock:calculo_agregado:{unidad}` | String | 10 s |

## Estructura

```
src/controladores  src/servicios  src/modelos  src/middlewares  src/rutas  src/config
web/               interfaz del monolito
db/postgres        esquema oficial + enlaces demo + recurso USUARIO
db/mongo           índices
docs/AUDITORIA.md  checklist del parcial
```

## Pruebas

```bash
npm test
```
