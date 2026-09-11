#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/apps/Electron_app"

export npm_config_ignore_scripts=false

if ! command -v npm >/dev/null 2>&1; then
  echo "Necesitas Node.js/npm para Electron." >&2
  exit 1
fi

if [ ! -x node_modules/.bin/electron ] && [ ! -e node_modules/electron/cli.js ]; then
  echo "Instalando dependencias de Electron (scripts de electron permitidos)…"
  npm install --ignore-scripts=false
fi

if [ ! -e node_modules/electron/dist/electron ] && [ -f node_modules/electron/install.js ]; then
  echo "Descargando binario de Electron…"
  (cd node_modules/electron && node install.js)
fi

echo "Abriendo catálogo XML. Flask debe estar en http://127.0.0.1:5001 (./run-flask.sh)."
exec npm start
