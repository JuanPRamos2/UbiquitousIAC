#!/usr/bin/env bash
# Prueba de humo: verifica que el ambiente quedó realmente operativo.
# No comprueba que el sistema esté "arriba" según Docker, sino que las
# tres piezas se contesten entre sí y que el mecanismo de privacidad
# diferencial responda.

set -uo pipefail

AMBIENTE="${1:-developer}"
case "$AMBIENTE" in
  developer) BASE="http://localhost:8000" ;;
  staging)   BASE="http://localhost" ;;
  production) BASE="${URL_PRODUCTION:-https://localhost}" ;;
esac

PASOS=0
FALLOS=0

verificar() {
  local nombre="$1"; shift
  PASOS=$((PASOS+1))
  if "$@" >/tmp/prueba.out 2>&1; then
    echo "  OK   $nombre"
  else
    echo "  FALLA $nombre"
    sed 's/^/        /' /tmp/prueba.out | head -5
    FALLOS=$((FALLOS+1))
  fi
}

echo "Prueba de humo — ambiente $AMBIENTE"

verificar "el proceso responde" \
  bash -c "curl -fsS --max-time 5 '$BASE/salud' | grep -q vivo"

verificar "el ambiente reportado es $AMBIENTE" \
  bash -c "curl -fsS --max-time 5 '$BASE/salud' | grep -q '\"$AMBIENTE\"'"

verificar "PostgreSQL y Redis contestan" \
  bash -c "curl -fsS --max-time 10 '$BASE/listo' | grep -q '\"estado\":\"listo\"'"

verificar "el agregado protegido se calcula" \
  bash -c "curl -sS --max-time 15 -H 'X-Actor-Id: USR-00003' \
           '$BASE/agregado/CAMP-2026-S1/UO-OPS-CC-T1' | grep -qE 'PUBLICADO|SUPRIMIDO'"

verificar "la segunda consulta llega desde la caché" \
  bash -c "curl -sS -D- -o /dev/null --max-time 10 -H 'X-Actor-Id: USR-00003' \
           '$BASE/agregado/CAMP-2026-S1/UO-OPS-CC-T1' | grep -qi 'X-Cache: HIT'"

echo "Resultado: $((PASOS-FALLOS))/$PASOS"
exit $(( FALLOS > 0 ? 1 : 0 ))
