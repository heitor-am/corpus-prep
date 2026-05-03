"""Parsers for trivial text formats: TXT, MD, CSV, JSON."""

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
    """Convert CSV into a textual representation: ``col: val | col: val`` per row.

    This format keeps column context inline with the value, which helps
    downstream tasks where the key-value relationship matters.
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
            raise ParserError(path, "CSV without header")

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
    """Serialize JSON with indent and ensure_ascii=False to preserve PT chars."""

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
            raise ParserError(path, f"invalid JSON: {exc.msg}") from exc

        text = json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False)
        return ParseResult(
            text=text,
            parser_name=self.name,
            char_count=len(text),
        )
