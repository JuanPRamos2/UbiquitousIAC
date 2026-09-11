# Electron_app

Cliente de escritorio. No reemplaza la librería: abre la web en :3000 y el microservicio Flask en :5001.

```bash
# En dos terminales, desde la raíz:
./run-library.sh
./run-flask.sh

# Luego:
cd apps/Electron_app
npm install
npm start
```

O `./run-electron.sh` desde la raíz (pide que 3000 y 5001 ya estén vivos).
