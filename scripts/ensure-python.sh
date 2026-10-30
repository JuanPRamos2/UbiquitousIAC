#!/usr/bin/env bash
# Crea .venv e instala las dependencias de los microservicios si faltan.
ensure_libreria_python() {
  local root="$1"
  local py="$root/.venv/bin/python"
  if [ ! -x "$py" ]; then
    python3 -m venv "$root/.venv"
  fi
  if ! "$py" -c "import flask, redis, jwt, bcrypt, dotenv, psycopg2, psycopg" >/dev/null 2>&1; then
    "$py" -m pip install -q \
      -r "$root/requirements.txt" \
      -r "$root/services/login/requirements.txt" \
      -r "$root/services/books/requirements.txt" \
      -r "$root/services/users/requirements.txt"
  fi
}
