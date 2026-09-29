# Librería (sin Ubiquitous)

Solo el software de la librería. El sitio HTML de Ubiquitous permanece en `main`.

```
app/services/soap/app.py   Flask (ruta de la práctica; carga services/soap)
apps/web-monolito/         Node :3000
apps/services/login/       Flask login :5000 (XML/JSON + Swagger)
apps/Electron_app/         escritorio: catálogo XML + portadas
apps/Python_app/           escritorio Python Tk: login, perfil, catálogo y CRUD
apps/desktop-classifier/   cliente Java SOAP
services/soap/             Flask SOAP + XML/JSON (código canónico)
data/database/             SQL
prompts/                   prompts
entrega/                   .tar.gz / .zip del monorepo
```

## Arranque

```bash
chmod +x run.sh run-flask.sh run-library.sh run-electron.sh run-login.sh run-tk.sh
./run-flask.sh       # http://127.0.0.1:5001
./run-login.sh       # http://127.0.0.1:5000/docs
./run-library.sh     # http://127.0.0.1:3000/library
./run-electron.sh    # catálogo XML con imágenes
./run-tk.sh          # apps/Python_app : login, perfil, catálogo y CRUD
```

| Puerto | Servicio |
| --- | --- |
| 3000 | Librería Node (alta/baja/cambio) |
| 5000 | Login Flask XML/JSON + Swagger |
| 5001 | Catálogo SOAP / XML / JSON. Lectura pública; escritura con JWT del login |
| 5433 | PostgreSQL Docker |

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
