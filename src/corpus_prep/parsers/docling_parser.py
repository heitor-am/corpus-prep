"""Docling — multi-format parser with embedded OCR (DOCX, PPTX, IMG, plus PDF fallback).

Does not register ``application/pdf`` in the global registry — pdf_native is the
default route for PDFs. When pdf_native flags ``needs_ocr=true``, the pipeline
instantiates DoclingParser directly and calls ``.parse(pdf_path)``.

OCR engine is configured to **EasyOCR with Portuguese** because Docling's default
RapidOCR / PP-OCRv4 is trained primarily for Chinese and English; on PT-BR
documents it loses spaces and confuses characters (``Picos`` -> ``Pic0S``).
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
    """Lazy singleton of DocumentConverter, configured for PT-BR OCR.

    Init is expensive: EasyOCR downloads its Portuguese weights on first use
    (~70 MB cached under ``~/.EasyOCR``). Subsequent calls reuse the singleton.
    """
    global _converter
    if _converter is None:
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import (
                EasyOcrOptions,
                PdfPipelineOptions,
            )
            from docling.document_converter import (
                DocumentConverter,
                ImageFormatOption,
                PdfFormatOption,
            )
        except ImportError as exc:
            raise ImportError(
                "Docling is not installed. Run: uv pip install docling"
            ) from exc

        ocr_options = EasyOcrOptions(lang=["pt"])
        pdf_options = PdfPipelineOptions(do_ocr=True, ocr_options=ocr_options)
        image_options = PdfPipelineOptions(do_ocr=True, ocr_options=ocr_options)

        _converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=image_options),
            }
        )
    return _converter  # type: ignore[no-any-return]


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
