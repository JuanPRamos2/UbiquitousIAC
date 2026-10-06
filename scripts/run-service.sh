#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
NAME="${1:?falta el nombre del servicio}"
PORT="${2:?falta el puerto}"
APP="$ROOT/services/$NAME"
cd "$APP"
if [ ! -f .env ]; then
  cp .env.example .env
fi
if [ -f "$ROOT/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
fi
export PYTHONPATH="$ROOT/services/shared:${PYTHONPATH:-}"
echo "$NAME → http://127.0.0.1:${PORT}"
exec python3 app.py
