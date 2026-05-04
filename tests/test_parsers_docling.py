"""Tests for DoclingParser. Docling install is opt-in (heavy)."""

from __future__ import annotations

import importlib.util

import pytest

from corpus_prep.parsers.docling_parser import (
    DOCLING_SUPPORTED_MIMES,
    DoclingParser,
    _reset_converter_for_tests,
)
from corpus_prep.parsers.registry import get_parser, is_supported

DOCLING_INSTALLED = importlib.util.find_spec("docling") is not None
slow = pytest.mark.slow


class TestDoclingParserSmoke:
    """Smoke tests that run without docling installed."""

    def test_supported_mime_types(self):
        parser = DoclingParser()
        assert set(parser.supported_mime_types) == set(DOCLING_SUPPORTED_MIMES)
        assert parser.name == "docling"

    def test_registered_for_office_formats(self):
        for mime in [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ]:
            assert is_supported(mime)
            instance = get_parser(mime)
            assert isinstance(instance, DoclingParser)

    def test_registered_for_image_formats(self):
        for mime in ["image/png", "image/jpeg", "image/tiff"]:
            assert is_supported(mime)
            instance = get_parser(mime)
            assert isinstance(instance, DoclingParser)

    def test_pdf_not_registered_under_docling(self):
        """PDF routes to pdf_native; docling stays reserved for the OCR fallback."""
        parser = get_parser("application/pdf")
        assert parser.name == "pdf-native"

    @pytest.mark.skipif(DOCLING_INSTALLED, reason="docling installed; ImportError test irrelevant")
    def test_parse_without_docling_raises_importerror(self, tmp_path):
        _reset_converter_for_tests()
        fake_path = tmp_path / "x.png"
        fake_path.write_bytes(b"not really png")
        with pytest.raises(ImportError, match="Docling"):
            DoclingParser().parse(fake_path)


@slow
@pytest.mark.skipif(not DOCLING_INSTALLED, reason="docling not installed")
class TestDoclingParserIntegration:
    """Real docling integration. Slow (loads layout / OCR models on first use)."""

    def test_parse_image(self, make_text_image):
        path = make_text_image(text="Hello world from corpus-prep")
        result = DoclingParser().parse(path)
        assert result.parser_name == "docling"
        assert result.metadata["backend"] == "docling"
        assert result.char_count > 0

    def test_parse_docx(self, make_docx):
        path = make_docx(
            paragraphs=[
                "Document title for Docling test",
                "Substantial paragraph that should survive the conversion.",
                "Second body paragraph with additional content.",
            ]
        )
        result = DoclingParser().parse(path)
        assert result.parser_name == "docling"
        assert result.char_count > 0
        assert "Document title" in result.text or "Substantial" in result.text

    def test_parse_pptx(self, make_pptx):
        path = make_pptx(
            slides=[
                ("Docling integration", "Body text on slide one"),
                ("Second slide", "Body text on slide two"),
            ]
        )
        result = DoclingParser().parse(path)
        assert result.parser_name == "docling"
        assert result.char_count > 0
        assert "Docling integration" in result.text or "slide one" in result.text
