#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

cleanup() {
  if [ -n "${LOGIN_PID:-}" ]; then kill "$LOGIN_PID" 2>/dev/null || true; fi
  if [ -n "${FLASK_PID:-}" ]; then kill "$FLASK_PID" 2>/dev/null || true; fi
  if [ -n "${NODE_PID:-}" ]; then kill "$NODE_PID" 2>/dev/null || true; fi
  if [ -n "${USERS_PID:-}" ]; then kill "$USERS_PID" 2>/dev/null || true; fi
  if [ -n "${AUTHORS_PID:-}" ]; then kill "$AUTHORS_PID" 2>/dev/null || true; fi
  if [ -n "${PEDIDOS_PID:-}" ]; then kill "$PEDIDOS_PID" 2>/dev/null || true; fi
  if [ -n "${PAGOS_PID:-}" ]; then kill "$PAGOS_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

"$ROOT/run-login.sh" &
LOGIN_PID=$!
"$ROOT/run-flask.sh" &
FLASK_PID=$!
"$ROOT/run-users.sh" &
USERS_PID=$!
"$ROOT/run-authors.sh" &
AUTHORS_PID=$!
"$ROOT/run-pedidos.sh" &
PEDIDOS_PID=$!
"$ROOT/run-pagos.sh" &
PAGOS_PID=$!
"$ROOT/run-library.sh" &
NODE_PID=$!

echo
echo "Login     →  http://127.0.0.1:5000/docs"
echo "Books     →  http://127.0.0.1:5001/books?format=json"
echo "Users     →  http://127.0.0.1:5002/users"
echo "Autores   →  http://127.0.0.1:5003/authors"
echo "Pedidos   →  http://127.0.0.1:5004/pedidos"
echo "Pagos     →  http://127.0.0.1:5005/pagos"
echo "Librería  →  http://127.0.0.1:3000/library"
echo "Tk        →  ./run-tk.sh"
echo
wait
