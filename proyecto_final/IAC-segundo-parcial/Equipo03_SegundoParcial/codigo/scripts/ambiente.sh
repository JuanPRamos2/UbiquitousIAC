#!/usr/bin/env bash
# Punto de entrada único para operar cualquiera de los tres ambientes.
#
#   ./scripts/ambiente.sh developer  arriba
#   ./scripts/ambiente.sh staging    abajo
#   ./scripts/ambiente.sh production estado
#
# Existe para que nadie tenga que recordar la combinación de archivos de
# compose, y para que sea imposible levantar production con el archivo de
# developer por accidente.

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AMBIENTE="${1:-}"
ACCION="${2:-arriba}"

case "$AMBIENTE" in
  developer|staging|production) ;;
  *)
    echo "Uso: $0 {developer|staging|production} {arriba|abajo|estado|bitacora|reconstruir|probar}" >&2
    exit 2
    ;;
esac

ARCHIVO_ENV="$RAIZ/infra/ambientes/$AMBIENTE.env"
if [[ ! -f "$ARCHIVO_ENV" ]]; then
  echo "ERROR: no existe $ARCHIVO_ENV" >&2
  echo "Copia el ejemplo:  cp infra/ambientes/$AMBIENTE.env.ejemplo $ARCHIVO_ENV" >&2
  exit 1
fi

# Guardia: production exige versión explícita de la imagen.
if [[ "$AMBIENTE" == "production" ]]; then
  if ! grep -qE '^VERSION=.+' "$ARCHIVO_ENV"; then
    echo "ERROR: production requiere VERSION en $ARCHIVO_ENV." >&2
    echo "       Desplegar 'local' o 'latest' en production está prohibido." >&2
    exit 1
  fi
fi

COMPOSE=(docker compose
  --project-name "bienestar-$AMBIENTE"
  --env-file "$ARCHIVO_ENV"
  -f "$RAIZ/infra/compose/docker-compose.base.yml"
  -f "$RAIZ/infra/compose/docker-compose.$AMBIENTE.yml")

case "$ACCION" in
  arriba)       "${COMPOSE[@]}" up -d --wait ;;
  abajo)        "${COMPOSE[@]}" down ;;
  borrar)       "${COMPOSE[@]}" down -v ;;
  estado)       "${COMPOSE[@]}" ps ;;
  bitacora)     "${COMPOSE[@]}" logs -f --tail=100 ;;
  reconstruir)  "${COMPOSE[@]}" build --no-cache && "${COMPOSE[@]}" up -d --wait ;;
  config)       "${COMPOSE[@]}" config ;;
  probar)       "$RAIZ/scripts/probar.sh" "$AMBIENTE" ;;
  *) echo "Acción desconocida: $ACCION" >&2; exit 2 ;;
esac
