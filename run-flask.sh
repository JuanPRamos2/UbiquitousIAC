#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/ensure-python.sh"
ensure_libreria_python "$ROOT"
export SOAP_DEMO="${SOAP_DEMO:-1}"
export PYTHONPATH="$ROOT/services/shared:$ROOT/services/books:${PYTHONPATH:-}"
exec "$ROOT/.venv/bin/python" serve.py
