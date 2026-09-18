# Electron_app

Cliente de escritorio que **consume el microservicio Flask en XML**.

Muestra de cada libro: **imagen (portada), título, autores, año de publicación, ISBN y precio**.

El campo de endpoint se guarda en **LocalStorage** (`library.soap.endpoint`). Por defecto usa `http://127.0.0.1:5001`.

## Arranque (Linux)

En la raíz del monorepo, Flask primero:

```bash
cd ~/Documents/Libreria
./run-flask.sh
```

En otra terminal, Electron:

```bash
cd ~/Documents/Libreria
./run-electron.sh
```

O a mano:

```bash
cd ~/Documents/Libreria/apps/Electron_app
rm -rf node_modules
npm install-scripts approve electron   # npm 11 bloquea el postinstall de Electron
npm install
npm start
```

Si aparece `Electron failed to install correctly`, el paquete npm está pero falta el binario. Bájalo:

```bash
cd ~/Documents/Libreria/apps/Electron_app
node node_modules/electron/install.js
npm start
```

En Arch, alternativa:

```bash
sudo pacman -S electron
cd ~/Documents/Libreria/apps/Electron_app
electron .
```

## Qué consume

| Recurso | Uso |
| --- | --- |
| `GET {endpoint}/books` | Catálogo XML completo (título, autores, año, ISBN, precio, `coverUrl`) |
| `GET {endpoint}/books-images` | Datos mínimos + portadas (`coverUrl` e `images[]`) |
| `GET {endpoint}/covers/{isbn}.svg` | Imagen de cada libro |

El microservicio canónico está en `services/soap/app.py`. La práctica pide también `app/services/soap/app.py`; ese archivo carga el mismo Flask.

Tus capturas: `apps/Electron_app/screenshots/`. Tu reflexión: `apps/Electron_app/REFLEXION.md`.
