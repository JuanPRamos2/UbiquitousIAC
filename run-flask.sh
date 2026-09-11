#!/usr/bin/env bash
# Microservicio Flask: SOAP + catálogo XML/JSON en :5001
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
export FLASK_APP=app.py
export SOAP_DEMO="${SOAP_DEMO:-1}"
exec python3 -m flask run --host=0.0.0.0 --port=5001
