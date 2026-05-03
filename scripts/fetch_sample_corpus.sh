#!/bin/bash
# Fetches the sample corpus (PT-BR diarios oficiais piauienses) into data/raw/.
#
# The corpus is hosted on a public Google Drive folder. Downloads via gdown
# (no OAuth needed as long as the folder is shared with "Anyone with the link").
#
# Drive imposes per-IP rate limits on public folder downloads, so the script
# wraps gdown in a retry loop. gdown skips files that already exist on disk,
# so re-running picks up where the previous attempt stopped.
#
# Override the source folder by exporting DRIVE_URL before running.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${TARGET_DIR:-$REPO_ROOT/data/raw}"
DRIVE_URL="${DRIVE_URL:-https://drive.google.com/drive/folders/1uG-b5wUw_KfzH1ZiRNfB7WzoUogrAa_I}"
MAX_RETRIES="${MAX_RETRIES:-5}"
RETRY_SLEEP_SECONDS="${RETRY_SLEEP_SECONDS:-60}"

# Resolve gdown — prefer the project venv if present.
if [ -x "$REPO_ROOT/.venv/bin/gdown" ]; then
  GDOWN="$REPO_ROOT/.venv/bin/gdown"
elif command -v gdown >/dev/null 2>&1; then
  GDOWN="gdown"
else
  echo "ERROR: gdown not found. Install with: uv pip install gdown" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"

echo "Source : $DRIVE_URL"
echo "Target : $TARGET_DIR"
echo "Retries: $MAX_RETRIES (sleep ${RETRY_SLEEP_SECONDS}s on rate limit)"
echo ""

attempt=1
while [ "$attempt" -le "$MAX_RETRIES" ]; do
  echo "--- Attempt $attempt/$MAX_RETRIES ---"
  if "$GDOWN" --folder "$DRIVE_URL" -O "$TARGET_DIR"; then
    echo ""
    echo "Done. Files in $TARGET_DIR:"
    file_count=$(find "$TARGET_DIR" -type f | wc -l)
    total_size=$(du -sh "$TARGET_DIR" | cut -f1)
    echo "  $file_count files, $total_size"
    exit 0
  fi
  echo ""
  echo "gdown failed (likely Drive rate limit). Sleeping ${RETRY_SLEEP_SECONDS}s before retry..."
  sleep "$RETRY_SLEEP_SECONDS"
  attempt=$((attempt + 1))
done

echo "" >&2
echo "ERROR: exhausted $MAX_RETRIES attempts. Some files may already be in $TARGET_DIR." >&2
echo "Re-run the script later — gdown will skip files already downloaded." >&2
exit 1
