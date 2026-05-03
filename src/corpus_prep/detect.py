"""MIME detection via Magika (Google) — supera python-magic em ~22-47% F1."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from magika import Magika

# Threshold de confiança abaixo do qual o resultado vai pra fallback.
DEFAULT_MIN_CONFIDENCE = 0.7
FALLBACK_MIME = "application/octet-stream"


@lru_cache(maxsize=1)
def _get_magika() -> Magika:
    """Singleton lazy do Magika — init carrega o modelo (~1MB, fast)."""
    from magika import Magika

    return Magika()


def detect_mime(
    path: Path, *, min_confidence: float = DEFAULT_MIN_CONFIDENCE
) -> str:
    """Retorna MIME type real do arquivo.

    Args:
        path: Caminho do arquivo.
        min_confidence: Score mínimo do Magika; abaixo disso retorna fallback.

    Returns:
        MIME type (ex.: 'application/pdf') ou 'application/octet-stream' se
        a detecção for incerta.

    Raises:
        FileNotFoundError: Se path não existir.
    """
    if not path.exists():
        raise FileNotFoundError(path)

    magika = _get_magika()
    result: Any = magika.identify_path(path)

    # API do Magika 0.6+: result.output.mime_type, result.score (top-level)
    score = float(getattr(result, "score", 1.0))
    if score < min_confidence:
        return FALLBACK_MIME

    mime = result.output.mime_type
    return str(mime)


def detect_with_score(path: Path) -> tuple[str, float]:
    """Versão que retorna (mime, confidence) sem aplicar threshold.

    Útil para diagnóstico ou ajuste fino do threshold em produção.
    """
    if not path.exists():
        raise FileNotFoundError(path)

    magika = _get_magika()
    result: Any = magika.identify_path(path)
    score = float(getattr(result, "score", 1.0))
    return str(result.output.mime_type), score


def _reset_cache_for_tests() -> None:
    """Limpa o singleton — usado em testes."""
    _get_magika.cache_clear()
