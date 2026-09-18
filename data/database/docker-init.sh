#!/bin/bash
# Solo corre la primera vez que se crea el volumen de Postgres.
set -euo pipefail
echo "Cargando esquema y semilla de la librería..."
for f in \
  01_schema.sql \
  02_seed_30_per_table.sql \
  04_stored_procedures.sql \
  05_triggers.sql \
  06_views.sql
do
  echo "  -> $f"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "/sql/$f"
done
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "/sql/07_grants.sql"
echo "Base library_db lista."
