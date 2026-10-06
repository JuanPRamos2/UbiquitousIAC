#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="$ROOT/apps/services/login"
cd "$APP"
if [ ! -f .env ]; then
  cp .env.example .env
fi
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python3 -m pip install -q -r requirements.txt
export PYTHONPATH="$ROOT/services/shared:${PYTHONPATH:-}"
exec python3 app.py
