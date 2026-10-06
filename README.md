# Librería (sin Ubiquitous)

Solo el software de la librería. El sitio HTML de Ubiquitous permanece en `main`.

```
app/services/soap/app.py   Flask (ruta de la práctica; carga services/soap)
apps/web-monolito/         Node :3000 (sigue hablando directo con PostgreSQL)
apps/services/login/       Flask login :5000 (XML/JSON + Swagger + Redis)
apps/Electron_app/         escritorio: catálogo XML + portadas
apps/Python_app/           escritorio Python Tk: CRUD de todos los microservicios
apps/desktop-classifier/   cliente Java SOAP
services/shared/           Redis, JWT y CORS compartidos
services/soap/             catálogo :5001 (código canónico de books)
services/users/            usuarios :5002
services/authors/          autores :5003
services/pedidos/          pedidos :5004
services/pagos/            pagos :5005
data/database/             SQL
prompts/                   prompts
entrega/                   .tar.gz / .zip del monorepo
```

## Arranque

```bash
chmod +x run.sh run-flask.sh run-library.sh run-electron.sh run-login.sh run-tk.sh
./run-flask.sh       # http://127.0.0.1:5001
./run-login.sh       # http://127.0.0.1:5000/docs
./run-users.sh       # http://127.0.0.1:5002
./run-authors.sh     # http://127.0.0.1:5003
./run-pedidos.sh     # http://127.0.0.1:5004
./run-pagos.sh       # http://127.0.0.1:5005
./run-library.sh     # http://127.0.0.1:3000/library
./run-electron.sh    # catálogo XML con imágenes
./run-tk.sh          # apps/Python_app : CRUD y semáforos

Redis (misma URL en los seis microservicios):

```bash
docker compose -f apps/web-monolito/docker-compose.yml up -d redis
# REDIS_URL=redis://:libreria-redis@127.0.0.1:6379/0
```
```

| Puerto | Servicio |
| --- | --- |
| 3000 | Librería Node (alta/baja/cambio) |
| 5000 | Login Flask XML/JSON + Swagger. Sesión y refresh en Redis. JWT 20 min |
| 5001 | Catálogo SOAP / XML / JSON. GET público con caché. Escritura con JWT de admin |
| 5002 | Users. Correo inmutable. Contraseña con tres valores |
| 5003 | Autores y su relación con libros. GET público |
| 5004 | Pedidos, líneas, stock y cancelación |
| 5005 | Pagos. Al registrar uno, el pedido pasa a pagado |
| 5433 | PostgreSQL Docker |
| 6379 | Redis |

Reflexión: `docs/REFLEXION_REDIS.md`. Animación: `docs/animacion/index.html`. Evidencia curl: `docs/EVIDENCIAS_REDIS.md`.

- Login Swagger: http://127.0.0.1:5000/docs
- Login UI (JSON): http://127.0.0.1:5000/ui
- XML catálogo: http://127.0.0.1:5001/books
- JSON: http://127.0.0.1:5001/books?format=json
- Mínimos + imágenes: http://127.0.0.1:5001/books-images
- Portada: http://127.0.0.1:5001/covers/9780451524935.svg
- SOAP: `POST` http://127.0.0.1:5001/soap
- Probar SOAP: http://127.0.0.1:5001/

La app Electron pide `/books` en XML, muestra **imagen, título, autores, año, ISBN y precio**, y guarda el endpoint en **LocalStorage**.

Si Electron falla al instalar, **no** apruebes el paquete antes de `npm install`. El binario se baja después:

```bash
cd apps/Electron_app
node node_modules/electron/install.js
npm start
```

En Arch, si eso falla: `sudo pacman -S electron` y luego `electron .` dentro de `apps/Electron_app`.

Admin: `mariana.solis@libreriaonline.mx` / `LibreriaAdmin26`

Capturas: `apps/Electron_app/screenshots/`. Reflexión: `apps/Electron_app/REFLEXION.md`.

Empaque (después de tus capturas): `./scripts/pack.sh` → `entrega/Libreria-monorepo.tar.gz` y `.zip`.
