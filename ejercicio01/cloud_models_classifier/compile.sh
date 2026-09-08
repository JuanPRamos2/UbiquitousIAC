#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if ! command -v javac >/dev/null 2>&1; then
  echo "No se encontró javac en el PATH. Ya instalaste Java: cierra y abre Kitty / code-oss."
  echo "Comprueba con: java -version && javac -version"
  exit 1
fi

mkdir -p bin
mapfile -t SOURCES < <(find src -name '*.java' | sort)
javac -encoding UTF-8 --release 11 -d bin "${SOURCES[@]}"
echo "Compilación correcta con $(javac -version 2>&1). Clases en: $ROOT/bin"
