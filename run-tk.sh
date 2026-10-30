#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if ! python3 -c "import tkinter" >/dev/null 2>&1; then
  echo "Falta Tk. En Debian/Ubuntu: sudo apt-get install -y python3-tk" >&2
  exit 1
fi
exec python3 "$ROOT/apps/Python_app/app.py"
