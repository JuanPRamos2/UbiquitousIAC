#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv 2>/dev/null || true
fi
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
python3 -m pip install -q -r requirements.txt
export SOAP_DEMO="${SOAP_DEMO:-1}"
export PYTHONPATH="$(pwd)/services/soap:${PYTHONPATH:-}"
exec python3 serve.py
