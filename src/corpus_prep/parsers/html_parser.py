"""HTML parser via Trafilatura — extracts main content while removing boilerplate."""

from __future__ import annotations

from pathlib import Path

import trafilatura

from corpus_prep.parsers.base import BaseParser, ParserError
from corpus_prep.parsers.registry import register
from corpus_prep.schemas import ParseResult
from corpus_prep.utils.io import read_text_with_fallback


@register("text/html")
class HTMLParser(BaseParser):
    """Trafilatura is the current SOTA (F1 0.945) for main-content extraction.

    Used by the RefinedWeb pipeline (Falcon LLM) and HuggingFace datatrove.
    """

    @property
    def name(self) -> str:
        return "html"

    @property
    def supported_mime_types(self) -> list[str]:
        return ["text/html"]

    def parse(self, path: Path) -> ParseResult:
        html = read_text_with_fallback(path)

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
        )

        # Fallback: pages without an obvious main element respond better with favor_recall.
        if text is None:
            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                favor_recall=True,
            )

        if text is None:
            raise ParserError(
                path, "trafilatura could not extract main content"
            )

        return ParseResult(
            text=text,
            parser_name=self.name,
            char_count=len(text),
        )
