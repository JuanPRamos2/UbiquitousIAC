# Librería (sin Ubiquitous)

Solo el software de la librería. El sitio HTML de Ubiquitous permanece en `main`.

```
apps/web-monolito/      Node :3000
apps/Electron_app/      escritorio
apps/desktop-classifier/  cliente Java SOAP
services/soap/          Flask SOAP + XML/JSON
data/database/          SQL
prompts/                prompts
```

## Arranque

```bash
chmod +x run.sh run-flask.sh run-library.sh run-electron.sh
./run-library.sh     # http://127.0.0.1:3000/library
./run-flask.sh       # http://127.0.0.1:5000  y  :5001
```

| Puerto | Servicio |
| --- | --- |
| 3000 | Librería Node (alta/baja/cambio) |
| 5000 | Flask SOAP / XML / JSON (mismo servicio) |
| 5001 | Flask SOAP / XML / JSON (mismo servicio) |
| 5433 | PostgreSQL Docker |

- XML: http://127.0.0.1:5001/books
- JSON: http://127.0.0.1:5001/books?format=json
- SOAP: `POST` http://127.0.0.1:5000/soap o `:5001/soap`
- Probar SOAP: http://127.0.0.1:5001/

Electron (con 3000 y 5001 ya arriba):

```bash
cd apps/Electron_app && npm install && npm start
```

Admin: `mariana.solis@libreriaonline.mx` / `LibreriaAdmin26`
