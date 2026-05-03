"""Tests for the PDFNativeParser (PyMuPDF4LLM)."""

from __future__ import annotations

import pytest

from corpus_prep.parsers.pdf_native import (
    SPARSE_THRESHOLD_CHARS_PER_PAGE,
    PDFNativeParser,
)


class TestPDFNativeParser:
    def test_native_pdf_with_text(self, make_native_pdf):
        # Long enough to clear the chars-per-page threshold.
        long_text = "\n".join(
            [
                "Hello world testing extraction in PDF format with native text layer.",
                "Second line of content keeps the chars-per-page count above the threshold.",
                "Third paragraph adds further density to the document for the heuristic.",
            ]
        )
        path = make_native_pdf(text=long_text)
        result = PDFNativeParser().parse(path)

        assert result.parser_name == "pdf-native"
        assert result.page_count == 1
        assert result.char_count > 0
        assert "Hello world" in result.text
        assert "Second line" in result.text
        assert result.metadata["extraction_method"] == "pymupdf4llm"
        assert "needs_ocr" not in result.metadata

    def test_blank_pdf_flags_needs_ocr(self, make_blank_pdf):
        path = make_blank_pdf()
        result = PDFNativeParser().parse(path)

        assert result.page_count == 1
        # Blank PDF has no extractable text -> chars_per_page = 0.
        assert result.char_count < SPARSE_THRESHOLD_CHARS_PER_PAGE
        assert result.metadata["needs_ocr"] == "true"
        assert float(result.metadata["chars_per_page"]) < SPARSE_THRESHOLD_CHARS_PER_PAGE

    def test_chars_per_page_metadata(self, make_native_pdf):
        path = make_native_pdf(text="Some text on the page.")
        result = PDFNativeParser().parse(path)
        assert "chars_per_page" in result.metadata
        # Must be parseable as float.
        float(result.metadata["chars_per_page"])

    def test_invalid_pdf_raises(self, write_file):
        path = write_file("notapdf.pdf", b"this is not a PDF")
        with pytest.raises(Exception):  # pymupdf raises FileDataError or similar
            PDFNativeParser().parse(path)

    def test_supported_mime_types(self):
        parser = PDFNativeParser()
        assert parser.supported_mime_types == ["application/pdf"]
        assert parser.name == "pdf-native"
