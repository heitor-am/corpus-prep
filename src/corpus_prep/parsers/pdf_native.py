"""PDF parser for PDFs with a selectable text layer, via PyMuPDF4LLM."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pymupdf4llm

from corpus_prep.parsers.base import BaseParser, ParserError
from corpus_prep.parsers.registry import register
from corpus_prep.schemas import ParseResult

# Heuristic: scanned PDFs rarely yield enough native text per page.
# Threshold (chars per page) comes from PRD section 7.2.3.
SPARSE_THRESHOLD_CHARS_PER_PAGE = 100.0


@register("application/pdf")
class PDFNativeParser(BaseParser):
    """PDFs with a real text layer extract instantly via PyMuPDF.

    Scanned PDFs (no text layer) yield a low ``chars_per_page`` ratio; this
    parser sets ``metadata.needs_ocr=true`` so the pipeline (M5) can re-route
    to DoclingParser. In M2 the flag is exposed but the rerouting itself is
    the orchestrator's responsibility, not the parser's.
    """

    @property
    def name(self) -> str:
        return "pdf-native"

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/pdf"]

    def parse(self, path: Path) -> ParseResult:
        try:
            doc = pymupdf.open(str(path))  # type: ignore[no-untyped-call]
        except Exception as exc:
            raise ParserError(path, f"pymupdf failed to open PDF: {exc}") from exc

        page_count = len(doc)
        doc.close()  # type: ignore[no-untyped-call]

        try:
            text = pymupdf4llm.to_markdown(str(path))
        except Exception as exc:
            raise ParserError(path, f"pymupdf4llm.to_markdown failed: {exc}") from exc

        char_count = len(text)
        chars_per_page = char_count / page_count if page_count > 0 else 0.0

        metadata = {
            "chars_per_page": f"{chars_per_page:.1f}",
            "extraction_method": "pymupdf4llm",
        }
        if chars_per_page < SPARSE_THRESHOLD_CHARS_PER_PAGE:
            metadata["needs_ocr"] = "true"

        return ParseResult(
            text=text,
            parser_name=self.name,
            char_count=char_count,
            page_count=page_count,
            metadata=metadata,
        )
