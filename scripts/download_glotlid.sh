#!/bin/bash
# Downloads the GlotLID v3 model into models/glotlid.bin.
#
# GlotLID v3 (CIS-LMU) is a FastText-based language identifier covering 2102
# languages and outperforming fasttext lid.176 on PT-BR. See cisnlp/GlotLID.
#
# The model file is ~120 MB — keep it out of git (`.gitignore` already covers
# `models/`).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${MODEL_DIR:-$REPO_ROOT/models}"
MODEL_PATH="$MODEL_DIR/glotlid.bin"

# GlotLID v3 binary on Hugging Face. Pin to a specific revision when you need
# reproducibility — `main` is the latest model version.
URL="${GLOTLID_URL:-https://huggingface.co/cis-lmu/glotlid/resolve/main/model_v3.bin}"

mkdir -p "$MODEL_DIR"

if [ -f "$MODEL_PATH" ]; then
  size=$(du -h "$MODEL_PATH" | cut -f1)
  echo "Model already present at $MODEL_PATH ($size). Skipping."
  exit 0
fi

echo "Downloading GlotLID v3 from $URL..."
curl -L --fail -o "$MODEL_PATH.tmp" "$URL"
mv "$MODEL_PATH.tmp" "$MODEL_PATH"

size=$(du -h "$MODEL_PATH" | cut -f1)
echo "Done. Model at $MODEL_PATH ($size)."
