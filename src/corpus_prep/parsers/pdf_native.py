"""PDF parser for PDFs with a selectable text layer, via PyMuPDF.

Uses ``page.get_text("text")`` rather than ``pymupdf4llm.to_markdown``. The
markdown variant is layout-aware, which sounds nicer in theory but can
silently drop the bulk of a page's content when the publisher places real
text inside vector graphics or styled overlays — common in Brazilian
official journals. Plain-text extraction is the safer default for training
corpora; we keep the page-level loop so we can preserve form-feed-style
breaks between pages.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

from corpus_prep.parsers.base import BaseParser, ParserError
from corpus_prep.parsers.registry import register
from corpus_prep.schemas import ParseResult

# Heuristic: scanned PDFs rarely yield enough native text per page.
SPARSE_THRESHOLD_CHARS_PER_PAGE = 100.0


@register("application/pdf")
class PDFNativeParser(BaseParser):
    """PDFs with a real text layer extract instantly via PyMuPDF.

    Scanned PDFs (no text layer) yield a low ``chars_per_page`` ratio; this
    parser sets ``metadata.needs_ocr=true`` so a downstream router can re-route
    to a real OCR engine.
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

        try:
            page_count = len(doc)
            page_texts = []
            for i in range(page_count):
                page = doc[i]
                page_texts.append(page.get_text("text"))  # type: ignore[no-untyped-call]
            text = "\n\n".join(page_texts)
        except Exception as exc:
            raise ParserError(path, f"pymupdf get_text failed: {exc}") from exc
        finally:
            doc.close()  # type: ignore[no-untyped-call]

        char_count = len(text)
        chars_per_page = char_count / page_count if page_count > 0 else 0.0

        metadata = {
            "chars_per_page": f"{chars_per_page:.1f}",
            "extraction_method": "pymupdf-text",
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
