#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
LIB="$ROOT/apps/web-monolito"
cd "$LIB"
if [ ! -f .env ]; then
  cp .env.example .env
fi
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-3000}"
npm install --omit=dev
bash scripts/ensure-db.sh
exec npm start
