#!/usr/bin/env bash
# Si Java está en el PATH (pacman), no hace falta nada más.
ROOT="$(cd "$(dirname "$0")" && pwd)"
if ! command -v java >/dev/null 2>&1; then
  echo "Java no está en el PATH. Abre una terminal nueva después de instalar el JDK."
fi
