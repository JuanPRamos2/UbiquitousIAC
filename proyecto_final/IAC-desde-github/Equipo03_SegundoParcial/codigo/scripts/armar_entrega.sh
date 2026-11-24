#!/usr/bin/env bash
# Arma el paquete de entrega, sin basura y de forma reproducible.
#
# POR QUÉ EXISTE
# --------------
# El paquete anterior se armó a mano y se fue con dump.rdb, .pytest_cache
# y los __pycache__ dentro. Eso no rompe nada y es exactamente el tipo de
# detalle que hace que una entrega «no se vea revisada», que fue parte de
# la retroalimentación del profesor.
#
# Con un guión, la lista de exclusiones está escrita una vez y el paquete
# sale igual siempre.
#
# Uso:
#   ./scripts/armar_entrega.sh [carpeta_de_salida]

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SALIDA="${1:-$RAIZ/../salida}"
NOMBRE="Parcial2_Correcciones_Emiliano_Gerardo"
ARMADO="$(mktemp -d)"
DESTINO="$ARMADO/$NOMBRE"

mkdir -p "$DESTINO/codigo" "$DESTINO/documentos" "$SALIDA"

# --------------------------------------------------------------------
# Lo que NO va
# --------------------------------------------------------------------
# Cada patrón está aquí por un motivo, no por precaución genérica:
#   __pycache__, .pytest_cache  artefactos de ejecución, se regeneran
#   node_modules                 300 MB que se bajan con npm install
#   dump.rdb                     volcado de Redis de una corrida local
#   .env                         credenciales reales; solo van los .ejemplo
#   *.pyc, .DS_Store             ruido
#   .git                         el historial no es parte de la entrega
# Se copia con `tar` y no con `rsync`: rsync no esta instalado en todas
# las maquinas del equipo, y tar viene con el sistema en las tres.
EXCLUIR=(
  --exclude=__pycache__ --exclude=.pytest_cache --exclude=node_modules
  --exclude=dump.rdb --exclude='*.pyc' --exclude=.DS_Store
  --exclude=.git --exclude='.env' --exclude='*.log'
  --exclude=venv --exclude=.venv --exclude=build --exclude=.gradle
  --exclude='*.zip'
)

echo "==> copiando el monorepo"
COPIAR=(apps contratos db infra pruebas scripts docs)
for archivo in README.md docker-compose.yml .gitignore .github; do
  [ -e "$RAIZ/$archivo" ] && COPIAR+=("$archivo")
done
tar -C "$RAIZ" "${EXCLUIR[@]}" -cf - "${COPIAR[@]}" \
  | tar -C "$DESTINO/codigo" -xf -

echo "==> copiando los documentos"
cp "$RAIZ"/docs/*.docx "$RAIZ"/docs/*.pdf "$DESTINO/documentos/" 2>/dev/null || true

# El LEEME va en la raiz del paquete: es lo primero que se abre, y si
# estuviera dentro de documentos/ compartiria lugar con siete .docx.
cp "$RAIZ/docs/LEEME_ENTREGA.md" "$DESTINO/LEEME.md"

# --------------------------------------------------------------------
# La comprobación que de verdad importa
# --------------------------------------------------------------------
# Un paquete con basura dentro no falla al abrirse, así que si no se
# comprueba aquí, nadie se entera hasta que lo abre quien revisa.
echo "==> revisando que no se fue basura"
PROBLEMAS=0
while IFS= read -r hallado; do
  echo "    SOBRA: $hallado"
  PROBLEMAS=$((PROBLEMAS + 1))
done < <(find "$DESTINO" \( -name '__pycache__' -o -name '.pytest_cache' \
           -o -name 'node_modules' -o -name 'dump.rdb' -o -name '*.pyc' \
           -o -name '.env' -o -name '*.zip' \) -print)

if [ "$PROBLEMAS" -gt 0 ]; then
  echo "Se encontraron $PROBLEMAS cosas que no deberian ir. No se arma."
  rm -rf "$ARMADO"
  exit 1
fi

# Los .env de ejemplo SÍ van: son las plantillas, sin credenciales.
echo "==> plantillas de ambiente incluidas:"
find "$DESTINO" -name '*.ejemplo' -o -name '*.example' | sed "s|$DESTINO|   |"

echo "==> armando el zip"
rm -f "$SALIDA/$NOMBRE.zip"
(cd "$ARMADO" && zip -rq "$SALIDA/$NOMBRE.zip" "$NOMBRE")
rm -rf "$ARMADO"

TAMANO="$(du -h "$SALIDA/$NOMBRE.zip" | cut -f1)"
ARCHIVOS="$(unzip -l "$SALIDA/$NOMBRE.zip" | tail -1 | awk '{print $2}')"
echo
echo "Listo: $SALIDA/$NOMBRE.zip  ($TAMANO, $ARCHIVOS archivos)"
