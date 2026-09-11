# Librería (sin Ubiquitous)

Solo el software de la librería. El sitio HTML de Ubiquitous permanece en `main`.

```
app/services/soap/app.py   Flask (ruta de la práctica; carga services/soap)
apps/web-monolito/         Node :3000
apps/Electron_app/         escritorio: catálogo XML + portadas
apps/desktop-classifier/   cliente Java SOAP
services/soap/             Flask SOAP + XML/JSON (código canónico)
data/database/             SQL
prompts/                   prompts
entrega/                   .tar.gz / .zip del monorepo
```

## Arranque

```bash
chmod +x run.sh run-flask.sh run-library.sh run-electron.sh
./run-flask.sh       # http://127.0.0.1:5000  y  :5001
./run-library.sh     # http://127.0.0.1:3000/library
./run-electron.sh    # catálogo XML con imágenes
```

| Puerto | Servicio |
| --- | --- |
| 3000 | Librería Node (alta/baja/cambio) |
| 5000 | Flask SOAP / XML / JSON (mismo servicio) |
| 5001 | Flask SOAP / XML / JSON (mismo servicio) |
| 5433 | PostgreSQL Docker |

- XML catálogo: http://127.0.0.1:5001/books
- JSON: http://127.0.0.1:5001/books?format=json
- Mínimos + imágenes: http://127.0.0.1:5001/books-images
- Portada: http://127.0.0.1:5001/covers/9780451524935.svg
- SOAP: `POST` http://127.0.0.1:5000/soap o `:5001/soap`
- Probar SOAP: http://127.0.0.1:5001/

La app Electron pide `/books` en XML, muestra **imagen, título, autores, año, ISBN y precio**, y guarda el endpoint en **LocalStorage**.

Si `npm` 11 bloquea Electron: `cd apps/Electron_app && npm install-scripts approve electron && npm install`.

Admin: `mariana.solis@libreriaonline.mx` / `LibreriaAdmin26`

Capturas: `apps/Electron_app/screenshots/`. Reflexión: `apps/Electron_app/REFLEXION.md`.

Empaque (después de tus capturas): `./scripts/pack.sh` → `entrega/Libreria-monorepo.tar.gz` y `.zip`.
