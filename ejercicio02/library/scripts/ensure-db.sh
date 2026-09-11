#!/usr/bin/env bash
# Levanta PostgreSQL (Docker) y carga el esquema si todavía no existe.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DEMO_PASSWORD="666"
DEMO_SECRET="libreria-demo-session-610248"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Se creó .env desde .env.example"
fi

fill_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=$" .env 2>/dev/null || ! grep -q "^${key}=" .env 2>/dev/null; then
    if grep -q "^${key}=" .env; then
      sed -i "s|^${key}=.*|${key}=${value}|" .env
    else
      echo "${key}=${value}" >> .env
    fi
  fi
}

fill_env DB_HOST 127.0.0.1
fill_env DB_PORT 5432
fill_env DB_NAME library_db
fill_env DB_USER library_user
fill_env DB_PASSWORD "$DEMO_PASSWORD"
fill_env SESSION_SECRET "$DEMO_SECRET"
fill_env HOST 0.0.0.0
fill_env PORT 3000

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  else
    docker-compose "$@"
  fi
}

if ! command -v docker >/dev/null 2>&1; then
  echo "No está Docker. Instálalo o crea library_db a mano y pon DB_PASSWORD en .env"
  echo "  cd ejercicio02/library && docker compose up -d"
  exit 1
fi

echo "Levantando PostgreSQL en el puerto 5432..."
compose up -d

echo "Esperando a que Postgres acepte conexiones..."
ready=0
for _ in $(seq 1 40); do
  if compose exec -T postgres pg_isready -U library_user -d library_db >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "Postgres no respondió. Revisa: docker compose logs postgres"
  exit 1
fi

has_books="$(compose exec -T postgres psql -U library_user -d library_db -tAc "SELECT to_regclass('public.books');" | tr -d '[:space:]')"
if [ "$has_books" != "books" ]; then
  echo "Cargando esquema y datos de demostración..."
  for f in \
    db/01_schema.sql \
    db/02_seed_30_per_table.sql \
    db/04_stored_procedures.sql \
    db/05_triggers.sql \
    db/06_views.sql
  do
    echo "  -> $f"
    compose exec -T postgres psql -U library_user -d library_db -v ON_ERROR_STOP=1 < "$f"
  done
else
  echo "El esquema ya está cargado."
fi

echo "Base lista. Usuario de prueba: mariana.solis@libreriaonline.mx / LibreriaAdmin26"
