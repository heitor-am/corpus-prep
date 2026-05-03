"""PDF parser para PDFs com camada de texto (selecionável), via PyMuPDF4LLM."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pymupdf4llm

from corpus_prep.parsers.base import BaseParser, ParserError
from corpus_prep.parsers.registry import register
from corpus_prep.schemas import ParseResult

# Heurística: PDFs escaneados raramente extraem texto suficiente.
# Threshold em chars/página vem do PRD §7.2.3.
SPARSE_THRESHOLD_CHARS_PER_PAGE = 100.0


@register("application/pdf")
class PDFNativeParser(BaseParser):
    """PDFs com camada de texto extraem instantaneamente via PyMuPDF.

    PDFs escaneados (sem camada de texto) produzem `chars_per_page` baixo;
    o parser marca `metadata.needs_ocr=true` e o pipeline (M5) re-roteia
    para DoclingParser. Em M2 a flag fica disponível mas o reroteamento é
    responsabilidade do orquestrador, não do parser.
    """

    @property
    def name(self) -> str:
        return "pdf-native"

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/pdf"]

    def parse(self, path: Path) -> ParseResult:
        try:
            doc = pymupdf.open(str(path))
        except Exception as exc:
            raise ParserError(path, f"pymupdf falhou ao abrir PDF: {exc}") from exc

        page_count = len(doc)
        doc.close()

        try:
            text = pymupdf4llm.to_markdown(str(path))
        except Exception as exc:
            raise ParserError(path, f"pymupdf4llm.to_markdown falhou: {exc}") from exc

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
