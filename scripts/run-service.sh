#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/ensure-python.sh"
ensure_libreria_python "$ROOT"
NAME="${1:?falta el nombre del servicio}"
PORT="${2:?falta el puerto}"
APP="$ROOT/services/$NAME"
cd "$APP"
if [ ! -f .env ]; then
  cp .env.example .env
fi
export PYTHONPATH="$ROOT/services/shared:${PYTHONPATH:-}"
echo "$NAME → http://127.0.0.1:${PORT}"
exec "$ROOT/.venv/bin/python" app.py
