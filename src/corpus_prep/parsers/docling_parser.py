"""Docling — multi-format parser with embedded OCR (DOCX, PPTX, IMG, plus PDF fallback).

Does not register ``application/pdf`` in the global registry — pdf_native is the
default route for PDFs. When pdf_native flags ``needs_ocr=true``, the pipeline
(M5) instantiates DoclingParser directly and calls ``.parse(pdf_path)``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from corpus_prep.parsers.base import BaseParser, ParserError
from corpus_prep.parsers.registry import register
from corpus_prep.schemas import ParseResult

if TYPE_CHECKING:
    from docling.document_converter import DocumentConverter


DOCLING_SUPPORTED_MIMES = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "image/png",
    "image/jpeg",
    "image/tiff",
)

_converter: Any = None


def _get_converter() -> DocumentConverter:
    """Lazy singleton of DocumentConverter — init is expensive (loads models)."""
    global _converter
    if _converter is None:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise ImportError(
                "Docling is not installed. Run: uv pip install docling"
            ) from exc
        _converter = DocumentConverter()
    return _converter


def _reset_converter_for_tests() -> None:
    """Test-only helper to clear the singleton."""
    global _converter
    _converter = None


@register(*DOCLING_SUPPORTED_MIMES)
class DoclingParser(BaseParser):
    @property
    def name(self) -> str:
        return "docling"

    @property
    def supported_mime_types(self) -> list[str]:
        return list(DOCLING_SUPPORTED_MIMES)

    def parse(self, path: Path) -> ParseResult:
        converter = _get_converter()
        try:
            result = converter.convert(str(path))
        except Exception as exc:
            raise ParserError(path, f"docling failed: {exc}") from exc

        text = result.document.export_to_markdown()
        return ParseResult(
            text=text,
            parser_name=self.name,
            char_count=len(text),
            metadata={"backend": "docling"},
        )
