#!/usr/bin/env bash
# Librería Node.js (alta / baja / cambio) en :3000
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
LIB="$ROOT/ejercicio02/library"
cd "$LIB"

if [ ! -f .env ]; then
  cp .env.example .env
  SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
  if command -v sed >/dev/null 2>&1; then
    sed -i "s/^SESSION_SECRET=.*/SESSION_SECRET=${SECRET}/" .env
    sed -i "s/^HOST=.*/HOST=0.0.0.0/" .env
    sed -i "s/^PORT=.*/PORT=3000/" .env
  fi
  echo "Se creó ejercicio02/library/.env (no lo subas a git)."
fi

export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-3000}"
npm install --omit=dev
exec npm start
