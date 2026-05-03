"""MIME detection via Magika (Google) — beats python-magic by ~22-47% F1."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from magika import Magika

# Confidence threshold below which the result falls back to octet-stream.
DEFAULT_MIN_CONFIDENCE = 0.7
FALLBACK_MIME = "application/octet-stream"


@lru_cache(maxsize=1)
def _get_magika() -> Magika:
    """Lazy Magika singleton — init loads the model (~1MB, fast)."""
    from magika import Magika

    return Magika()


def detect_mime(
    path: Path, *, min_confidence: float = DEFAULT_MIN_CONFIDENCE
) -> str:
    """Return the file's real MIME type.

    Args:
        path: File path.
        min_confidence: Minimum Magika score; below it returns the fallback MIME.

    Returns:
        MIME type (e.g. ``application/pdf``) or ``application/octet-stream``
        when detection is uncertain.

    Raises:
        FileNotFoundError: when ``path`` does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(path)

    magika = _get_magika()
    result: Any = magika.identify_path(path)

    # Magika 0.6+ API: result.output.mime_type, result.score (top-level).
    score = float(getattr(result, "score", 1.0))
    if score < min_confidence:
        return FALLBACK_MIME

    mime = result.output.mime_type
    return str(mime)


def detect_with_score(path: Path) -> tuple[str, float]:
    """Return ``(mime, confidence)`` without applying the threshold.

    Useful for diagnostics or fine-tuning the threshold in production.
    """
    if not path.exists():
        raise FileNotFoundError(path)

    magika = _get_magika()
    result: Any = magika.identify_path(path)
    score = float(getattr(result, "score", 1.0))
    return str(result.output.mime_type), score


def _reset_cache_for_tests() -> None:
    """Test-only helper to clear the singleton."""
    _get_magika.cache_clear()
