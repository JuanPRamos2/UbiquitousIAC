#!/usr/bin/env bash
# Levanta el sistema web en la máquina, SIN Docker, en el puerto 8000.
#
# Compañero de scripts/arrancar_microservicios.sh: ese levanta los nueve
# servicios, este levanta el portal que los consume.
#
# POR QUÉ EXPORTA LAS DIRECCIONES DE LOS NUEVE SERVICIOS
# ------------------------------------------------------
# El portal lee cada dirección de una variable de ambiente y, si falta, la
# pantalla correspondiente lo dice en lugar de inventarse datos. Eso está
# bien hecho, pero tenía un efecto desconcertante al arrancar a mano: el
# portal levantaba, todas las pantallas respondían, y cada una avisaba que
# «este ambiente no tiene configurada la direccion de <servicio>». El
# sistema parecía roto cuando lo único que faltaba eran las variables.
#
# Con docker compose no pasa, porque el compose las define. Esta es la vía
# sin Docker, así que las define aquí.
#
# Uso:
#   ./scripts/arrancar_web.sh            # lo levanta
#   ./scripts/arrancar_web.sh detener    # lo baja

set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUERTO="${PUERTO_WEB:-8000}"
BITACORA="${BITACORA_WEB:-/tmp/web.log}"

detener() {
  # Se mata por puerto, no por patrón de línea de comandos: un patrón como
  # "wsgi:app" también coincide con el propio pgrep de este script, y el
  # efecto es que el script se mata a sí mismo antes de terminar.
  local pids
  pids="$(lsof -t -i ":$PUERTO" -sTCP:LISTEN 2>/dev/null | sort -u)"
  for pid in $pids; do kill "$pid" 2>/dev/null; done
  sleep 1
}

if [ "${1:-arriba}" = "detener" ] || [ "${1:-}" = "abajo" ]; then
  detener
  echo "Sistema web detenido."
  exit 0
fi

detener

export PG_HOST="${PG_HOST:-127.0.0.1}"
export PG_BASE="${PG_BASE:-bienestar_limpio}"
export PG_USUARIO="${PG_USUARIO:-bienestar_app}"
export PG_CLAVE="${PG_CLAVE:-desarrollo_local}"
export REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
export APP_AMBIENTE="${APP_AMBIENTE:-developer}"
export MOSTRAR_ERRORES="${MOSTRAR_ERRORES:-true}"
export GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"

# El mismo secreto que usan los nueve microservicios: es lo que hace que un
# token emitido por auth-service se valide en todos ellos.
export JWT_SECRETO="${JWT_SECRETO:-secreto_de_desarrollo_local}"

export AUTH_SERVICE_URL="${AUTH_SERVICE_URL:-http://127.0.0.1:8101}"
export USERS_SERVICE_URL="${USERS_SERVICE_URL:-http://127.0.0.1:8102}"
export CATALOG_SERVICE_URL="${CATALOG_SERVICE_URL:-http://127.0.0.1:8103}"
export MAIN_PROCESS_SERVICE_URL="${MAIN_PROCESS_SERVICE_URL:-http://127.0.0.1:8104}"
export DOCUMENTS_SERVICE_URL="${DOCUMENTS_SERVICE_URL:-http://127.0.0.1:8105}"
export NOTIFICATIONS_SERVICE_URL="${NOTIFICATIONS_SERVICE_URL:-http://127.0.0.1:8106}"
export QUERIES_SERVICE_URL="${QUERIES_SERVICE_URL:-http://127.0.0.1:8107}"
export REPORTS_SERVICE_URL="${REPORTS_SERVICE_URL:-http://127.0.0.1:8108}"
export ALGORITHMS_SERVICE_URL="${ALGORITHMS_SERVICE_URL:-http://127.0.0.1:8109}"

cd "$RAIZ/apps/web"
setsid nohup python3 -m gunicorn -c gunicorn.conf.py \
  --bind "127.0.0.1:$PUERTO" wsgi:app > "$BITACORA" 2>&1 < /dev/null &

sleep 5
codigo="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 \
          "http://127.0.0.1:$PUERTO/listo" 2>/dev/null || echo 000)"
if [ "$codigo" = "200" ]; then
  echo "Portal arriba en http://127.0.0.1:$PUERTO  (bitácora: $BITACORA)"
else
  echo "El portal respondió $codigo. Revisa $BITACORA" >&2
  tail -15 "$BITACORA" >&2
  exit 1
fi
