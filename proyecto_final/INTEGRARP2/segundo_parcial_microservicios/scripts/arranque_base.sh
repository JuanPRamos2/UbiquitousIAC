#!/usr/bin/env bash
# Reproduce fuera de Docker la cadena de arranque de la base de datos,
# en el mismo orden en que la ejecuta el contenedor de PostgreSQL.
#
# Sirve para dos cosas:
#   1. Probar la cadena sin depender de poder descargar imágenes.
#   2. Cargar la base en una instancia de PostgreSQL ya instalada.
#
#   ./scripts/arranque_base.sh bienestar_dev [--con-semilla]

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${1:-bienestar_dev}"
SEMILLA="${2:-}"

export PG_USUARIO="${PG_USUARIO:-bienestar_app}"
export PG_CLAVE="${PG_CLAVE:-desarrollo_local}"
export POSTGRES_USER="${POSTGRES_USER:-postgres}"
export POSTGRES_DB="$BASE"

ejecutar_sql() { psql -v ON_ERROR_STOP=1 -q -d "$BASE" -f "$1"; }

echo "==> 00  rol de aplicación"
bash "$RAIZ/db/esquema/00_rol_aplicacion.sh" >/dev/null

echo "==> 01  esquema"
ejecutar_sql "$RAIZ/db/esquema/01_esquema.sql"

if [[ "$SEMILLA" == "--con-semilla" ]]; then
  echo "==> 02  volumen sintético"
  ejecutar_sql "$RAIZ/db/semilla/02_volumen_sintetico.sql"
fi

echo "==> 05  migración 001 (rol motor y funciones SECURITY DEFINER)"
ejecutar_sql "$RAIZ/db/migraciones/001_rol_motor_y_funciones_definer.sql"

echo "==> 09  permisos de menor privilegio"
bash "$RAIZ/db/esquema/09_permisos.sh" >/dev/null

echo "Base $BASE lista."
