#!/usr/bin/env bash
# Corre los seis perfiles contra la IP pública de GCP y resume los CSV.
# Uso: ./ejecutar_perfiles.sh <ip_publica>
set -u

RAIZ="$(cd "$(dirname "$0")" && pwd)"
cd "$RAIZ"
IP="${1:-${LOCUST_TARGET_IP:-}}"
EVIDENCIAS="$RAIZ/evidencias"
mkdir -p "$EVIDENCIAS"

if [ -z "$IP" ]; then
  echo "Indica la IP pública: ./ejecutar_perfiles.sh <ip_publica>" >&2
  exit 1
fi
case "$IP" in
  localhost|127.*|0.0.0.0|::1)
    echo "Rechazado: $IP es local. Usa la IP externa de la instancia GCP." >&2
    exit 1
    ;;
esac

if ! command -v locust >/dev/null 2>&1; then
  echo "No está el comando locust. Instálalo con: python3 -m pip install -r requirements.txt" >&2
  exit 1
fi

export LOCUST_TARGET_IP="$IP"
: >"$EVIDENCIAS/errores.log"
echo "IP objetivo: $IP" | tee "$EVIDENCIAS/smoke_manual.txt"
echo "Credenciales de entorno: $([ -n "${LOCUST_EMAIL:-}" ] && [ -n "${LOCUST_PASSWORD:-}" ] && echo presentes || echo ausentes)" | tee -a "$EVIDENCIAS/smoke_manual.txt"

probar() {
  local nombre="$1"
  local url="$2"
  local codigo
  codigo="$(curl -sS -m 15 -o /dev/null -w '%{http_code}' "$url" 2>>"$EVIDENCIAS/errores.log" || echo "curl_fallo")"
  echo "$nombre $url -> $codigo" | tee -a "$EVIDENCIAS/smoke_manual.txt"
}

echo "--- comprobación manual previa a la carga ---" | tee -a "$EVIDENCIAS/smoke_manual.txt"
probar monolito "http://${IP}:3000/"
probar monolito_salud "http://${IP}:3000/library/health"
probar login "http://${IP}:5000/health?format=json"
probar books "http://${IP}:5001/health?format=json"
probar books_catalogo "http://${IP}:5001/books?format=json"
probar users "http://${IP}:5002/health?format=json"
probar autores "http://${IP}:5003/health?format=json"
probar autores_lista "http://${IP}:5003/authors"
probar pedidos "http://${IP}:5004/health?format=json"
probar pagos "http://${IP}:5005/health?format=json"

correr() {
  local perfil="$1"
  local tope="$2"
  echo "Inicia perfil $perfil (tope de seguridad ${tope})."
  if ! LOCUST_PROFILE="$perfil" locust -f "$RAIZ/locustfile.py" --headless \
    --run-time "$tope" \
    --csv "$EVIDENCIAS/$perfil" \
    --html "$EVIDENCIAS/$perfil.html"; then
    echo "El perfil $perfil terminó con error. Se continúa con el siguiente." | tee -a "$EVIDENCIAS/errores.log"
  fi
}

correr smoke 40s
correr load 140s
correr stress 200s
correr spike 140s
correr soak 260s
correr breakpoint 260s

python3 "$RAIZ/resumir_csv.py"
echo "Listo. Revisa evidencias/, RESULTADOS.md y REFLEXION.md."
