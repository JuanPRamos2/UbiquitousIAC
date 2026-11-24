#!/usr/bin/env bash
# Levanta los dieciséis microservicios en la máquina, SIN Docker.
#
# POR QUÉ EXISTE
# --------------
# La vía normal es `./scripts/ambiente.sh developer arriba`, que usa
# docker compose. Pero las dos aplicaciones cliente (la de escritorio y la
# móvil) y la demostración se prueban contra servicios que respondan, y en
# una máquina sin acceso a Docker Hub el compose no puede bajar las
# imágenes. Este script cubre ese caso: mismos puertos, mismas variables,
# mismo comportamiento, sin contenedores.
#
# No sustituye al compose para entregar ni para desplegar. Es la vía de
# desarrollo y la que usa el guión de demostración cuando Docker no está.
#
# Uso:
#   ./scripts/arrancar_microservicios.sh            # levanta todo
#   ./scripts/arrancar_microservicios.sh detener    # los baja
#   ./scripts/arrancar_microservicios.sh estado     # sondea cada uno

set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BITACORAS="${BITACORAS_MICROSERVICIOS:-/tmp/microservicios}"
mkdir -p "$BITACORAS"

export PG_HOST="${PG_HOST:-127.0.0.1}"
export PG_BASE="${PG_BASE:-bienestar_limpio}"
export PG_USUARIO="${PG_USUARIO:-bienestar_app}"
export PG_CLAVE="${PG_CLAVE:-desarrollo_local}"
export REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
export APP_AMBIENTE="${APP_AMBIENTE:-developer}"
# El mismo secreto en los veinticuatro componentes: es lo que hace que un token
# emitido por auth-service (Python) se valide en catalog-service (Node).
export JWT_SECRETO="${JWT_SECRETO:-secreto_de_desarrollo_local}"

# nombre:puerto:lenguaje. El orden es el de los puertos 8101-8124.
SERVICIOS=(
  "auth-service:8101:python"
  "users-service:8102:python"
  "catalog-service:8103:node"
  "main-process-service:8104:node"
  "documents-service:8105:python"
  "notifications-service:8106:python"
  "queries-service:8107:python"
  "reports-service:8108:python"
  "algorithms-service:8109:python"
  "consent-service:8110:python"
  "privacy-service:8111:python"
  "survey-service:8112:node"
  "indicators-service:8113:node"
  "trends-service:8114:python"
  "interventions-service:8115:python"
  "support-service:8116:node"
  "organizational-service:8117:node"
  "audit-service:8118:python"
  "data-governance-service:8119:python"
  "sync-service:8120:python"
  "export-service:8121:python"
  "configuration-service:8122:python"
  "monitoring-service:8123:python"
  "integration-service:8124:python"
)

# monitoring-service sondea a los demas por 127.0.0.1 y su puerto, que es
# lo correcto fuera de Docker. Dentro de Docker resuelve por nombre de
# servicio, y eso lo activa MONITOREO_EN_DOCKER en el compose: aqui NO se
# pone, porque fuera de Docker esos nombres no resuelven y el panel
# reportaria los dieciseis como caidos.

detener() {
  # Se mata por puerto y no por patrón de línea de comandos: un patrón como
  # "gunicorn" también coincide con el propio pgrep de este script, y el
  # efecto es que el script se suicida con código 144 antes de terminar.
  for entrada in "${SERVICIOS[@]}"; do
    local puerto="${entrada#*:}"; puerto="${puerto%%:*}"
    local pids
    pids="$(lsof -t -i ":$puerto" -sTCP:LISTEN 2>/dev/null | sort -u)"
    for pid in $pids; do
      kill "$pid" 2>/dev/null
    done
  done
  sleep 1
}

estado() {
  local fallos=0
  for entrada in "${SERVICIOS[@]}"; do
    local nombre="${entrada%%:*}"
    local puerto="${entrada#*:}"; puerto="${puerto%%:*}"
    local codigo respuesta estado faltan
    respuesta="$(curl -sS --max-time 4 \
                 "http://127.0.0.1:$puerto/health/ready" 2>/dev/null)"
    codigo="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 4 \
              "http://127.0.0.1:$puerto/health/ready" 2>/dev/null || echo 000)"
    # El estado se lee del cuerpo y no se deduce del codigo: la sonda
    # distingue "listo", "degradado" (200, atiende con una dependencia
    # opcional caida) y "no_listo" (503). Mirar solo el codigo juntaria
    # "listo" con "degradado" y ocultaria justo lo que hay que ver.
    estado="$(printf '%s' "$respuesta" | grep -o '"estado":"[a-z_]*"' |
              head -1 | cut -d'"' -f4)"
    faltan="$(printf '%s' "$respuesta" |
              grep -o '"\(degradado_por\|falta\)":\[[^]]*\]' |
              head -1 | sed 's/.*\[//; s/\]//; s/"//g')"
    if [ "$estado" = "listo" ]; then
      printf '  OK      %-24s puerto %s\n' "$nombre" "$puerto"
    elif [ "$estado" = "degradado" ]; then
      printf '  DEGRAD. %-24s puerto %s (atiende sin: %s)\n' \
             "$nombre" "$puerto" "${faltan:-?}"
    elif [ "$codigo" = "503" ]; then
      printf '  NO_LISTO %-23s puerto %s (le falta: %s)\n' \
             "$nombre" "$puerto" "${faltan:-?}"
    else
      printf '  CAIDO   %-24s puerto %s (codigo %s, ver %s/%s.log)\n' \
             "$nombre" "$puerto" "$codigo" "$BITACORAS" "$nombre"
      fallos=$((fallos+1))
    fi
  done
  return $fallos
}

case "${1:-arriba}" in
  detener|abajo) detener; echo "Microservicios detenidos."; exit 0 ;;
  estado)        estado; exit $? ;;
esac

detener

for entrada in "${SERVICIOS[@]}"; do
  nombre="${entrada%%:*}"
  resto="${entrada#*:}"
  puerto="${resto%%:*}"
  lenguaje="${resto##*:}"
  ruta="$RAIZ/apps/microservicios/$nombre"

  if [ ! -d "$ruta" ]; then
    echo "  OMITIDO $nombre (no existe $ruta)"
    continue
  fi

  if [ "$lenguaje" = "node" ]; then
    if [ ! -d "$ruta/node_modules" ]; then
      echo "  OMITIDO $nombre (falta npm install)"
      continue
    fi
    (cd "$ruta" && PUERTO="$puerto" NOMBRE_SERVICIO="$nombre" \
       setsid nohup node src/server.js \
       > "$BITACORAS/$nombre.log" 2>&1 < /dev/null &)
  else
    (cd "$ruta" && PUERTO="$puerto" NOMBRE_SERVICIO="$nombre" \
       setsid nohup python3 -m gunicorn --bind "127.0.0.1:$puerto" \
         --workers 2 --timeout 60 --access-logfile - app:app \
       > "$BITACORAS/$nombre.log" 2>&1 < /dev/null &)
  fi
done

# Las sondas tardan: PostgreSQL abre su pool y Redis su conexión en la
# primera petición, no al arrancar el proceso.
sleep 6
echo "Microservicios (bitácoras en $BITACORAS):"
estado
