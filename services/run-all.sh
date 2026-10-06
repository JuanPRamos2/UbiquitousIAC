#!/usr/bin/env bash
# Arranca login, books, users, autores, pedidos y pagos, y muestra si responden.
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/ensure-python.sh"
ensure_libreria_python "$ROOT"
RUN_DIR="$ROOT/services/.run"
mkdir -p "$RUN_DIR"

NAMES=(login books users autores pedidos pagos)
DIRS=(login books users authors pedidos pagos)
PORTS=(5000 5001 5002 5003 5004 5005)
PIDS=()
OWNED=()

python_for() {
  local dir="$1"
  if [ -x "$dir/.venv/bin/python" ]; then
    echo "$dir/.venv/bin/python"
  elif [ -x "$ROOT/.venv/bin/python" ]; then
    echo "$ROOT/.venv/bin/python"
  else
    echo python3
  fi
}

listening() {
  curl -sS -m 1 -o /dev/null "http://127.0.0.1:$1/health" 2>/dev/null
}

start_one() {
  local index="$1"
  local dir="$ROOT/services/${DIRS[$index]}"
  local name="${NAMES[$index]}"
  local port="${PORTS[$index]}"
  local py
  py="$(python_for "$dir")"
  if [ ! -f "$dir/.env" ] && [ -f "$dir/.env.example" ]; then
    cp "$dir/.env.example" "$dir/.env"
  fi
  (
    cd "$dir"
    export PYTHONPATH="$ROOT/services/shared${PYTHONPATH:+:$PYTHONPATH}"
    if [ "$name" = "books" ]; then
      export SOAP_DEMO=1
    fi
    exec "$py" app.py
  ) >"$RUN_DIR/$name.log" 2>&1 &
  PIDS[$index]=$!
  OWNED[$index]=1
}

stop_owned() {
  local index pid
  for index in "${!PIDS[@]}"; do
    if [ "${OWNED[$index]:-0}" = 1 ]; then
      pid="${PIDS[$index]}"
      if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
      fi
    fi
  done
}

trap 'stop_owned; printf "\nMicroservicios detenidos.\n"; exit 0' INT TERM

for index in "${!NAMES[@]}"; do
  if listening "${PORTS[$index]}"; then
    PIDS[$index]=""
    OWNED[$index]=0
  else
    start_one "$index"
  fi
done

probe() {
  local index pid port name
  local watch=()
  for index in "${!NAMES[@]}"; do
    name="${NAMES[$index]}"
    port="${PORTS[$index]}"
    pid="${PIDS[$index]}"
    if [ "${OWNED[$index]}" = 1 ] && { [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; }; then
      printf '%s' "detenido" >"$RUN_DIR/$name.http"
      continue
    fi
    (
      code="$(curl -sS -m 8 -o /dev/null -w '%{http_code}' "http://127.0.0.1:${port}/health" 2>/dev/null || true)"
      if [ -z "$code" ] || [ "$code" = "000" ]; then
        printf '%s' "sin respuesta" >"$RUN_DIR/$name.http"
      elif [ "$code" = "200" ]; then
        printf '%s' "corriendo" >"$RUN_DIR/$name.http"
      else
        printf '%s' "corriendo (health ${code})" >"$RUN_DIR/$name.http"
      fi
    ) &
    watch+=($!)
  done
  if [ "${#watch[@]}" -gt 0 ]; then
    wait "${watch[@]}"
  fi
}

estado() {
  local name="${NAMES[$1]}"
  if [ -f "$RUN_DIR/$name.http" ]; then
    cat "$RUN_DIR/$name.http"
  else
    echo "sin respuesta"
  fi
}

draw() {
  local index
  probe
  echo "Microservicios"
  printf '%-14s %-8s %s\n' "microservicio" "puerto" "estado"
  for index in "${!NAMES[@]}"; do
    printf '%-14s %-8s %s\n' "${NAMES[$index]}" "${PORTS[$index]}" "$(estado "$index")"
  done
  echo
  echo "Ctrl+C detiene los que arrancó este comando."
  echo "Logs: services/.run/"
}

echo "Arrancando microservicios..."
for _ in 1 2 3 4 5 6 7 8; do
  probe
  pending=0
  for index in "${!NAMES[@]}"; do
    if [ "$(estado "$index")" = "sin respuesta" ]; then
      pending=1
    fi
  done
  if [ "$pending" = 0 ]; then
    break
  fi
  sleep 1
done

draw
wait
