# UbiquitousIAC

Monorepo de la librería. Las aplicaciones viven en `apps/`, no en `app/`.

```
UbiquitousIAC/
  apps/web-monolito/     librería Node (puerto 3000)
  apps/Electron_app/     escritorio Electron (abre la librería y el SOAP)
  services/soap/         Flask SOAP + XML/JSON (puerto 5001)
  data/database/         SQL, semilla y permisos
  prompts/               prompts de los ejercicios
  ejercicio01/ …         sitio Ubiquitous (HTML de evidencias)
```

## Arranque

```bash
cd ~/Documents/UbiquitousIAC
chmod +x run.sh run-flask.sh run-library.sh run-electron.sh

# 1) Base + librería HTML
./run-library.sh          # http://127.0.0.1:3000/library

# 2) SOAP / XML / JSON
./run-flask.sh            # http://127.0.0.1:5001

# 3) Escritorio (opcional, con 1 y 2 ya corriendo)
cd apps/Electron_app && npm install && npm start
```

O todo el backend: `./run.sh`

| Puerto | Qué es |
| --- | --- |
| 3000 | Librería (login, alta/baja/cambio) |
| 5001 | Flask: XML por defecto, JSON con `?format=json`, SOAP en `POST /soap` |
| 5433 | PostgreSQL (Docker) |

Admin: `mariana.solis@libreriaonline.mx` / `LibreriaAdmin26`

## READMEs y prompts

- Este archivo: mapa del monorepo
- `apps/web-monolito/README.md` — librería Node
- `services/soap/README.md` — microservicio Flask
- `apps/Electron_app/README.md` — cliente de escritorio
- `data/README.md` — base de datos
- `prompts/` — prompts de la materia
