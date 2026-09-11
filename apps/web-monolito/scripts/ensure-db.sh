#!/usr/bin/env bash
# Levanta PostgreSQL en Docker (puerto 5433) y deja listo el esquema.
# Usa 5433 para no chocar con un Postgres del sistema en 5432.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DEMO_PASSWORD="666"
DEMO_SECRET="libreria-demo-session-610248"
DEMO_PORT="5433"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Se creó .env desde .env.example"
fi

set_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    echo "${key}=${value}" >> .env
  fi
}

set_env DB_HOST 127.0.0.1
set_env DB_PORT "$DEMO_PORT"
set_env DB_NAME library_db
set_env DB_USER library_user
set_env DB_PASSWORD "$DEMO_PASSWORD"
set_env SESSION_SECRET "$DEMO_SECRET"
set_env HOST 0.0.0.0
set_env PORT 3000

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  else
    docker-compose "$@"
  fi
}

SQL_DIR="$(cd "$ROOT/../../data/database" && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  echo "No está Docker. Instálalo o crea library_db a mano y pon DB_PASSWORD en .env"
  echo "  cd apps/web-monolito && docker compose up -d"
  exit 1
fi

echo "Levantando PostgreSQL en el puerto ${DEMO_PORT}..."
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
    "$SQL_DIR"/01_schema.sql \
    "$SQL_DIR"/02_seed_30_per_table.sql \
    "$SQL_DIR"/04_stored_procedures.sql \
    "$SQL_DIR"/05_triggers.sql \
    "$SQL_DIR"/06_views.sql
  do
    echo "  -> $f"
    compose exec -T postgres psql -U library_user -d library_db -v ON_ERROR_STOP=1 < "$f"
  done
else
  echo "El esquema ya está cargado."
fi

echo "Otorgando permisos a library_user..."
compose exec -T postgres psql -U library_user -d library_db -v ON_ERROR_STOP=1 < "$SQL_DIR"/07_grants.sql
compose exec -T postgres psql -U library_user -d library_db -v ON_ERROR_STOP=1 <<'SQL'
DO $$
DECLARE
  obj RECORD;
BEGIN
  FOR obj IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
  LOOP
    EXECUTE format('ALTER TABLE public.%I OWNER TO library_user', obj.tablename);
  END LOOP;
  FOR obj IN SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public'
  LOOP
    EXECUTE format('ALTER SEQUENCE public.%I OWNER TO library_user', obj.sequence_name);
  END LOOP;
END $$;
SQL

echo "Base lista en 127.0.0.1:${DEMO_PORT}"
echo "Prueba: mariana.solis@libreriaonline.mx / LibreriaAdmin26"
