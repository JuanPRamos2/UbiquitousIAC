#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
export SOAP_DEMO="${SOAP_DEMO:-1}"
export PYTHONPATH="$(pwd)/services/soap:${PYTHONPATH:-}"
exec python3 serve.py
