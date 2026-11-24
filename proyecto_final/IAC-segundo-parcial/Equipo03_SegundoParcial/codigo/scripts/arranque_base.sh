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

# Las migraciones se recorren con un glob ordenado, NO con una lista
# escrita a mano. La lista a mano fue un error real: este guion corria solo
# la migracion 001, y los archivos de compose por ambiente montaban solo
# esa misma. Una base recien creada levantaba, respondia su sonda de salud,
# y fallaba al primer uso real con un error de tabla inexistente. Lo que lo
# hacia dificil es que «levanta bien» y «funciona» no eran lo mismo, y la
# sonda decia lo primero.
#
# Con el glob, agregar una migracion no obliga a acordarse de este archivo.
echo "==> migraciones"
for archivo in "$RAIZ"/db/migraciones/*.sql; do
  echo "    $(basename "$archivo")"
  ejecutar_sql "$archivo"
done

# Los permisos van DESPUES de las migraciones: la 004 crea tablas y
# columnas sobre las que este script otorga privilegios.
echo "==> permisos de menor privilegio"
bash "$RAIZ/db/esquema/09_permisos.sh" >/dev/null

# Las semillas van al final, igual que en el contenedor: la 03, la 04 y la
# 05 insertan sobre objetos que crean las migraciones.
if [[ "$SEMILLA" == "--con-semilla" ]]; then
  echo "==> semillas"
  for archivo in "$RAIZ"/db/semilla/*.sql; do
    echo "    $(basename "$archivo")"
    ejecutar_sql "$archivo"
  done
fi

echo "Base $BASE lista."
