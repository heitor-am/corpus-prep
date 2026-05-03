"""HTML parser via Trafilatura — extrai conteúdo principal removendo boilerplate."""

from __future__ import annotations

from pathlib import Path

import trafilatura

from corpus_prep.parsers.base import BaseParser, ParserError
from corpus_prep.parsers.registry import register
from corpus_prep.schemas import ParseResult
from corpus_prep.utils.io import read_text_with_fallback


@register("text/html")
class HTMLParser(BaseParser):
    """Trafilatura é o atual SOTA (F1 0.945) para extração de conteúdo principal.

    Usado também no pipeline RefinedWeb (Falcon LLM) e HuggingFace datatrove.
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

        # Fallback: páginas sem main-content evidente respondem melhor com favor_recall.
        if text is None:
            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                favor_recall=True,
            )

        if text is None:
            raise ParserError(
                path, "trafilatura nao conseguiu extrair conteudo principal"
            )

        return ParseResult(
            text=text,
            parser_name=self.name,
            char_count=len(text),
        )
