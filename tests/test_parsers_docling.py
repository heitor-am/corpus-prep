"""Testes do DoclingParser. A instalação do docling é opt-in (pesada)."""

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
    """Smoke tests que rodam sem docling instalado."""

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
        """PDF é roteado para pdf_native; docling fica reservado para fallback OCR."""
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
    """Integração real com docling. Lento (carrega modelos no primeiro uso)."""

    def test_parse_image(self, tmp_path):
        # Gera PNG simples com texto via PIL
        from PIL import Image, ImageDraw

        img_path = tmp_path / "sample.png"
        img = Image.new("RGB", (400, 100), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((20, 30), "Hello world from corpus-prep", fill="black")
        img.save(img_path)

        result = DoclingParser().parse(img_path)
        assert result.parser_name == "docling"
        assert result.metadata["backend"] == "docling"
        assert result.char_count > 0
