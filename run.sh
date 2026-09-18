#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

cleanup() {
  if [ -n "${FLASK_PID:-}" ]; then kill "$FLASK_PID" 2>/dev/null || true; fi
  if [ -n "${NODE_PID:-}" ]; then kill "$NODE_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

"$ROOT/run-flask.sh" &
FLASK_PID=$!
"$ROOT/run-library.sh" &
NODE_PID=$!

echo
echo "Librería  →  http://127.0.0.1:3000/library"
echo "Flask     →  http://127.0.0.1:5001/books?format=json"
echo "Electron  →  cd apps/Electron_app && npm start"
echo
wait
