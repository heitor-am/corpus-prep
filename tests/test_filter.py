"""Tests for the filter module — uses a mock LanguagePredictor to skip real models."""

from __future__ import annotations

from dataclasses import dataclass

from corpus_prep.filter import (
    DEFAULT_PT_LABEL,
    FilterConfig,
    FilterResult,
    is_valid,
)


@dataclass
class MockLangPredictor:
    """Predictor that always returns the configured label and confidence."""

    label: str = DEFAULT_PT_LABEL
    confidence: float = 0.99

    def predict(self, text: str) -> tuple[str, float]:  # noqa: ARG002
        return self.label, self.confidence


def _long_pt_text(min_chars: int = 200) -> str:
    """Generate a valid PT-BR text with chars > min and good word diversity."""
    return (
        "O processamento de linguagem natural permite que computadores "
        "compreendam o significado de textos escritos. Modelos modernos "
        "utilizam redes neurais profundas baseadas em transformers para "
        "alcancar resultados expressivos em diversas tarefas. " * 2
    )


class TestLengthFilter:
    def test_short_text_rejected(self):
        result = is_valid("texto curto", FilterConfig(min_chars=200), MockLangPredictor())
        assert result.passed is False
        assert result.rejected_by == "length"
        # Length is the first filter — it never reaches the LID.
        assert result.detected_language is None

    def test_long_enough_passes_length(self):
        result = is_valid(_long_pt_text(), FilterConfig(), MockLangPredictor())
        assert result.passed is True


class TestLanguageFilter:
    def test_wrong_language_high_confidence_rejected(self):
        result = is_valid(
            _long_pt_text(),
            FilterConfig(),
            MockLangPredictor(label="eng_Latn", confidence=0.95),
        )
        assert result.passed is False
        assert result.rejected_by == "language"
        assert result.detected_language == "eng_Latn"
        assert result.language_confidence == 0.95

    def test_wrong_language_low_confidence_passes(self):
        # Confidence below min_lang_confidence -> filter does not fire.
        result = is_valid(
            _long_pt_text(),
            FilterConfig(min_lang_confidence=0.5),
            MockLangPredictor(label="eng_Latn", confidence=0.3),
        )
        # Passes because LID is uncertain.
        assert result.passed is True

    def test_correct_language_passes(self):
        result = is_valid(_long_pt_text(), FilterConfig(), MockLangPredictor())
        assert result.passed is True
        assert result.detected_language == DEFAULT_PT_LABEL


class TestRepetitionFilter:
    def test_low_diversity_rejected(self):
        # 200+ chars but a single repeated word.
        text = "palavra " * 50
        result = is_valid(
            text, FilterConfig(min_unique_word_ratio=0.1), MockLangPredictor()
        )
        assert result.passed is False
        assert result.rejected_by == "repetition"

    def test_high_diversity_passes(self):
        result = is_valid(_long_pt_text(), FilterConfig(), MockLangPredictor())
        assert result.passed is True


class TestCharRatioFilter:
    def test_too_many_non_alpha_rejected(self):
        # Long text but more than 50% non-alphabetic.
        text = "abc " + "1234567890 " * 50
        result = is_valid(
            text,
            FilterConfig(max_non_alpha_ratio=0.5, min_unique_word_ratio=0.0),
            MockLangPredictor(),
        )
        assert result.passed is False
        assert result.rejected_by == "char_ratio"

    def test_normal_alpha_ratio_passes(self):
        result = is_valid(_long_pt_text(), FilterConfig(), MockLangPredictor())
        assert result.passed is True


class TestFilterPriority:
    """Filters apply in order: length -> language -> repetition -> char_ratio."""

    def test_length_short_circuits_language(self):
        # A very short text must NOT consult the LID — short circuit.
        result = is_valid(
            "abc",
            FilterConfig(min_chars=200),
            MockLangPredictor(label="eng_Latn", confidence=0.99),
        )
        assert result.rejected_by == "length"


class TestFilterResultMetadata:
    def test_passing_result_includes_lang_metadata(self):
        result = is_valid(
            _long_pt_text(),
            FilterConfig(),
            MockLangPredictor(label="por_Latn", confidence=0.97),
        )
        assert result.passed is True
        assert result.detected_language == "por_Latn"
        assert result.language_confidence == 0.97
