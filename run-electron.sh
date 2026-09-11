#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/apps/Electron_app"

export npm_config_ignore_scripts=false

if ! command -v npm >/dev/null 2>&1; then
  echo "Necesitas Node.js/npm." >&2
  exit 1
fi

if [ ! -d node_modules/electron ]; then
  npm install --ignore-scripts=false
fi

npm install-scripts approve electron >/dev/null 2>&1 || true

if [ ! -f node_modules/electron/path.txt ] && [ -f node_modules/electron/install.js ]; then
  echo "Descargando el binario de Electron (tarda un poco)…"
  node node_modules/electron/install.js
fi

if [ -f node_modules/electron/path.txt ]; then
  echo "Abriendo catálogo XML. Flask debe estar en http://127.0.0.1:5001"
  exec npm start
fi

if command -v electron >/dev/null 2>&1; then
  echo "Usando Electron del sistema (pacman)."
  exec electron .
fi

echo "Electron no descargó el binario. En Arch:" >&2
echo "  sudo pacman -S electron" >&2
echo "  cd ~/Documents/Libreria/apps/Electron_app && electron ." >&2
exit 1
