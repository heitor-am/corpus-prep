"""Filtros de qualidade e identificação de idioma.

Pipeline:
    1. min_chars      — descarta textos muito curtos
    2. language       — descarta se idioma detectado != esperado (com confiança)
    3. repetition     — descarta textos com vocabulário pobre (likely OCR garbage)
    4. char_ratio     — descarta textos com muitos não-alfabéticos (likely OCR garbage)

Cada descarte registra o motivo. O orquestrador (M5) agrega em FilterStats.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    pass


# Default: GlotLID rotula PT-BR como 'por_Latn'.
DEFAULT_PT_LABEL = "por_Latn"
DEFAULT_GLOTLID_PATH = Path("models/glotlid.bin")

# Truncamento da entrada do FastText: GlotLID lida com sentenças, não documentos.
LID_MAX_CHARS = 1000


@dataclass(frozen=True)
class FilterConfig:
    """Configuração dos filtros de qualidade."""

    min_chars: int = 200
    expected_language: str = DEFAULT_PT_LABEL
    min_lang_confidence: float = 0.5
    max_non_alpha_ratio: float = 0.5
    min_unique_word_ratio: float = 0.1


@dataclass
class FilterResult:
    """Resultado da avaliação de um documento."""

    passed: bool
    rejected_by: str | None = None
    detected_language: str | None = None
    language_confidence: float | None = None


class LanguagePredictor(Protocol):
    """Contrato para identificadores de idioma — facilita mock em testes."""

    def predict(self, text: str) -> tuple[str, float]:
        """Retorna (label, confidence) para o texto."""
        ...


class LanguageIdentifier:
    """Wrapper sobre fasttext + modelo GlotLID v3.

    GlotLID supera fasttext lid.176 em PT-BR e cobre 2102 idiomas. Modelo é
    baixado via scripts/download_glotlid.sh para `models/glotlid.bin`.
    """

    def __init__(self, model_path: Path = DEFAULT_GLOTLID_PATH) -> None:
        self.model_path = model_path
        self._model: Any = None

    def _load(self) -> None:
        if self._model is not None:
            return
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Modelo GlotLID nao encontrado em {self.model_path}. "
                "Rode scripts/download_glotlid.sh primeiro."
            )
        import fasttext

        self._model = fasttext.load_model(str(self.model_path))

    def predict(self, text: str) -> tuple[str, float]:
        """Retorna (label, confidence). Trunca texto a LID_MAX_CHARS.

        FastText espera entrada de uma única linha — qualquer newline embutido
        é convertido em espaço.
        """
        self._load()
        sample = text.replace("\n", " ")[:LID_MAX_CHARS]
        labels, probs = self._model.predict(sample, k=1)
        label = labels[0].replace("__label__", "")
        return label, float(probs[0])


def is_valid(
    text: str, config: FilterConfig, lang_id: LanguagePredictor
) -> FilterResult:
    """Aplica os 4 filtros sequencialmente. Retorna FilterResult.

    A ordem é importante — filtros baratos primeiro (length antes de LID).
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
