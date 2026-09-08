#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "$ROOT/env.sh"
"$ROOT/compile.sh"
java -cp "$ROOT/bin" CloudClassifierApp
