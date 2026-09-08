#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "$ROOT/env.sh"
"$ROOT/compile.sh"
if [[ $# -eq 0 ]]; then
  echo "Uso: ./run-cli.sh \"máquinas virtuales almacenamiento redes\""
  exit 1
fi
java -cp "$ROOT/bin" CloudClassifier "$@"
