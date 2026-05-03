"""Quality and language filters.

Pipeline:
    1. min_chars      — drop documents that are too short
    2. language       — drop when detected language != expected (above confidence)
    3. repetition     — drop documents with poor vocabulary diversity (likely OCR garbage)
    4. char_ratio     — drop documents dominated by non-alphabetic chars (likely OCR garbage)

Each rejection records its reason. The orchestrator (M5) aggregates these
into FilterStats.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

# Default: GlotLID labels Brazilian Portuguese as 'por_Latn'.
DEFAULT_PT_LABEL = "por_Latn"
DEFAULT_GLOTLID_PATH = Path("models/glotlid.bin")

# FastText input cap: GlotLID is trained on sentences, not full documents.
LID_MAX_CHARS = 1000


@dataclass(frozen=True)
class FilterConfig:
    """Configuration for the quality filters."""

    min_chars: int = 200
    expected_language: str = DEFAULT_PT_LABEL
    min_lang_confidence: float = 0.5
    max_non_alpha_ratio: float = 0.5
    min_unique_word_ratio: float = 0.1


@dataclass
class FilterResult:
    """Outcome of evaluating a single document."""

    passed: bool
    rejected_by: str | None = None
    detected_language: str | None = None
    language_confidence: float | None = None


class LanguagePredictor(Protocol):
    """Protocol for language identifiers — keeps tests easy to mock."""

    def predict(self, text: str) -> tuple[str, float]:
        """Return ``(label, confidence)`` for the input text."""
        ...


class LanguageIdentifier:
    """Thin wrapper around fasttext + the GlotLID v3 model.

    GlotLID outperforms fasttext lid.176 on PT-BR and covers 2102 languages.
    The model is fetched by ``scripts/download_glotlid.sh`` into
    ``models/glotlid.bin``.
    """

    def __init__(self, model_path: Path = DEFAULT_GLOTLID_PATH) -> None:
        self.model_path = model_path
        self._model: Any = None

    def _load(self) -> None:
        if self._model is not None:
            return
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"GlotLID model not found at {self.model_path}. "
                "Run scripts/download_glotlid.sh first."
            )
        import fasttext

        self._model = fasttext.load_model(str(self.model_path))

    def predict(self, text: str) -> tuple[str, float]:
        """Return ``(label, confidence)``. Truncates input to LID_MAX_CHARS.

        FastText expects single-line input — embedded newlines are converted
        to spaces.
        """
        self._load()
        sample = text.replace("\n", " ")[:LID_MAX_CHARS]
        labels, probs = self._model.predict(sample, k=1)
        label = labels[0].replace("__label__", "")
        return label, float(probs[0])


def is_valid(
    text: str, config: FilterConfig, lang_id: LanguagePredictor
) -> FilterResult:
    """Apply the four filters in order. Cheap filters run first.

    Length is checked before LID so we never invoke the model on garbage input.
    """
    if len(text) < config.min_chars:
        return FilterResult(passed=False, rejected_by="length")

    label, confidence = lang_id.predict(text)
    if (
        label != config.expected_language
        and confidence > config.min_lang_confidence
    ):
        return FilterResult(
            passed=False,
            rejected_by="language",
            detected_language=label,
            language_confidence=confidence,
        )

    words = text.split()
    if words:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < config.min_unique_word_ratio:
            return FilterResult(
                passed=False,
                rejected_by="repetition",
                detected_language=label,
                language_confidence=confidence,
            )

    alpha_count = sum(1 for c in text if c.isalpha())
    non_alpha_ratio = 1.0 - (alpha_count / len(text)) if text else 1.0
    if non_alpha_ratio > config.max_non_alpha_ratio:
        return FilterResult(
            passed=False,
            rejected_by="char_ratio",
            detected_language=label,
            language_confidence=confidence,
        )

    return FilterResult(
        passed=True,
        detected_language=label,
        language_confidence=confidence,
    )
