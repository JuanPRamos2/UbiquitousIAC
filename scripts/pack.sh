#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$ROOT/entrega"
mkdir -p "$OUT_DIR"
cd "$ROOT"

tar -czf "$OUT_DIR/Libreria-monorepo.tar.gz" \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='entrega' \
  --exclude='*.pyc' \
  app apps services data prompts \
  app.py serve.py requirements.txt README.md \
  run.sh run-flask.sh run-library.sh run-electron.sh \
  scripts

if command -v zip >/dev/null 2>&1; then
  rm -f "$OUT_DIR/Libreria-monorepo.zip"
  zip -qr "$OUT_DIR/Libreria-monorepo.zip" \
    app apps services data prompts \
    app.py serve.py requirements.txt README.md \
    run.sh run-flask.sh run-library.sh run-electron.sh \
    scripts \
    -x '*/node_modules/*' '*/.venv/*' '*/__pycache__/*' '*/.git/*' 'entrega/*'
fi

ls -lh "$OUT_DIR"
echo "Listo: $OUT_DIR/Libreria-monorepo.tar.gz"
