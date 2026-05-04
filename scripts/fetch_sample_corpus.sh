#!/bin/bash
# Fetches a sample corpus (PT-BR diarios oficiais) into data/<name>/.
#
# Two ways to invoke:
#
#   ./scripts/fetch_sample_corpus.sh <name>
#       Look <name> up in the table below and download the matching folder
#       into data/<name>/.
#
#   DRIVE_URL=... TARGET_DIR=... ./scripts/fetch_sample_corpus.sh
#       Manual override for arbitrary Drive folders.
#
# Drive imposes per-IP rate limits on public-folder downloads, so the script
# wraps gdown in a retry loop. gdown skips files already on disk, so re-running
# picks up where the previous attempt stopped.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Known corpora: name -> Drive folder URL.
declare -A CORPORA=(
  [vale-do-caninde]="https://drive.google.com/drive/folders/1ZRbnc0NMi1MxiP1FSpRdOxVolnfFQnSt"
  [serra-da-capivara]="https://drive.google.com/drive/folders/1uG-b5wUw_KfzH1ZiRNfB7WzoUogrAa_I"
)

# Resolve target dir + URL from either positional arg or env vars.
NAME="${1:-}"
if [ -n "$NAME" ]; then
  if [ -z "${CORPORA[$NAME]:-}" ]; then
    echo "ERROR: unknown corpus '$NAME'." >&2
    echo "Available: ${!CORPORA[*]}" >&2
    echo "Or set DRIVE_URL and TARGET_DIR env vars to override." >&2
    exit 1
  fi
  TARGET_DIR="${TARGET_DIR:-$REPO_ROOT/data/$NAME}"
  DRIVE_URL="${DRIVE_URL:-${CORPORA[$NAME]}}"
else
  TARGET_DIR="${TARGET_DIR:-$REPO_ROOT/data/raw}"
  if [ -z "${DRIVE_URL:-}" ]; then
    echo "ERROR: no corpus name given and DRIVE_URL not set." >&2
    echo "Usage:" >&2
    echo "  $0 <name>           # known: ${!CORPORA[*]}" >&2
    echo "  DRIVE_URL=... $0    # any Drive folder" >&2
    exit 1
  fi
fi

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
