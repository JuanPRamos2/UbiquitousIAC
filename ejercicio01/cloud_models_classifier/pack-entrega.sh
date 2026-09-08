#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
DEST="$ROOT/web/descargas"
OUT="$DEST/610248_EG01_cloud_models_classifier.zip"
mkdir -p "$DEST"
cp "$ROOT/README.md" "$DEST/README.md"

python - "$ROOT" "$OUT" <<'PY'
import os, sys, zipfile
root, out = sys.argv[1], sys.argv[2]
skip_parts = {".jdk", "bin", ".git"}
if os.path.exists(out):
    os.remove(out)
base = os.path.basename(root)
parent = os.path.dirname(root)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, parent)
        parts = set(rel_dir.split(os.sep))
        if skip_parts & parts:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in skip_parts]
        for name in filenames:
            if name.endswith(".class"):
                continue
            if name.endswith(".zip") and "descargas" in rel_dir:
                continue
            full = os.path.join(dirpath, name)
            arc = os.path.join(rel_dir, name)
            zf.write(full, arc)
    print("archivos en el zip:", len(zf.namelist()))
PY

echo "Listo:"
ls -lh "$DEST/README.md" "$OUT"

