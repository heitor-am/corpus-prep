"""Parsers para formatos texto triviais: TXT, MD, CSV, JSON."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from corpus_prep.parsers.base import BaseParser, ParserError
from corpus_prep.parsers.registry import register
from corpus_prep.schemas import ParseResult
from corpus_prep.utils.io import read_text_with_fallback as _read_text


@register("text/plain")
class PlainTextParser(BaseParser):
    @property
    def name(self) -> str:
        return "plaintext"

    @property
    def supported_mime_types(self) -> list[str]:
        return ["text/plain"]

    def parse(self, path: Path) -> ParseResult:
        text = _read_text(path)
        return ParseResult(
            text=text,
            parser_name=self.name,
            char_count=len(text),
        )


@register("text/markdown")
class MarkdownParser(BaseParser):
    @property
    def name(self) -> str:
        return "markdown"

    @property
    def supported_mime_types(self) -> list[str]:
        return ["text/markdown"]

    def parse(self, path: Path) -> ParseResult:
        text = _read_text(path)
        return ParseResult(
            text=text,
            parser_name=self.name,
            char_count=len(text),
        )


@register("text/csv")
class CSVParser(BaseParser):
    """Converte CSV em uma representação textual `col: val | col: val` por linha.

    Esse formato preserva o contexto das colunas no texto extraído, o que ajuda
    em tarefas downstream onde a relação chave-valor importa.
    """

    @property
    def name(self) -> str:
        return "csv"

    @property
    def supported_mime_types(self) -> list[str]:
        return ["text/csv"]

    def parse(self, path: Path) -> ParseResult:
        raw = _read_text(path)
        reader = csv.DictReader(io.StringIO(raw))
        if reader.fieldnames is None:
            raise ParserError(path, "CSV sem header")

        lines = [
            " | ".join(f"{col}: {row.get(col, '')}" for col in reader.fieldnames)
            for row in reader
        ]
        text = "\n".join(lines)
        return ParseResult(
            text=text,
            parser_name=self.name,
            char_count=len(text),
            metadata={"rows": str(len(lines)), "columns": str(len(reader.fieldnames))},
        )


@register("application/json")
class JSONParser(BaseParser):
    """Serializa JSON com indentação e sem escape de caracteres não-ASCII (preserva PT)."""

    @property
    def name(self) -> str:
        return "json"

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/json"]

    def parse(self, path: Path) -> ParseResult:
        raw = _read_text(path)
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ParserError(path, f"JSON inválido: {exc.msg}") from exc

        text = json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False)
        return ParseResult(
            text=text,
            parser_name=self.name,
            char_count=len(text),
        )
