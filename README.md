# Librería (sin Ubiquitous)

Solo el software de la librería. El sitio HTML de Ubiquitous permanece en `main`.

```
app/services/soap/app.py   ruta de la práctica; carga services/books
apps/web-monolito/         Node :3000 (sigue hablando directo con PostgreSQL)
apps/Electron_app/         escritorio: catálogo XML + portadas
apps/Python_app/           escritorio Python Tk: CRUD de todos los microservicios
apps/desktop-classifier/   cliente Java SOAP
services/shared/           Redis, JWT y CORS compartidos
services/login/            login :5000
services/books/            catálogo :5001
services/users/            usuarios :5002
services/authors/          autores :5003
services/pedidos/          pedidos :5004
services/pagos/            pagos :5005
data/database/             SQL
prompts/                   prompts
entrega/                   .tar.gz / .zip del monorepo
```

## Arranque

Hace falta Docker, Python 3.10 o superior y, para la app de escritorio, Tk (`python3-tk`).

```bash
docker compose -f apps/web-monolito/docker-compose.yml up -d postgres redis
cd services
./run-all.sh
```

Eso crea el entorno de Python si no existe, copia cada `.env.example` a `.env` y levanta los seis microservicios. En otra terminal, desde la raíz:

```bash
./run-tk.sh
```

Admin: `mariana.solis@libreriaonline.mx` / `LibreriaAdmin26`

Para arrancar uno solo, desde la raíz: `./run-login.sh`, `./run-flask.sh`, `./run-users.sh`, `./run-authors.sh`, `./run-pedidos.sh` o `./run-pagos.sh`. El monolito Node es `./run-library.sh` y Electron es `./run-electron.sh`. Redis usa `redis://:libreria-redis@127.0.0.1:6379/0`.

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

Animación: `docs/animacion/index.html`. Evidencia curl: `docs/EVIDENCIAS_REDIS.md`.

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
