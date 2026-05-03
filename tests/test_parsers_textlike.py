"""Tests for the trivial text-format parsers."""

from __future__ import annotations

import json

import pytest

from corpus_prep.parsers.base import ParserError
from corpus_prep.parsers.textlike import (
    CSVParser,
    JSONParser,
    MarkdownParser,
    PlainTextParser,
)


class TestPlainTextParser:
    def test_utf8(self, write_file):
        # Sample data intentionally in PT to exercise the encoding path.
        path = write_file("a.txt", "olá mundo, ção é fácil")
        result = PlainTextParser().parse(path)
        assert result.text == "olá mundo, ção é fácil"
        assert result.parser_name == "plaintext"
        assert result.char_count == len(result.text)

    def test_latin1_fallback(self, write_file):
        path = write_file("a.txt", "olá mundo".encode("latin-1"))
        result = PlainTextParser().parse(path)
        assert "olá mundo" in result.text  # latin-1 decodes 'á' correctly

    def test_empty_file(self, write_file):
        path = write_file("empty.txt", "")
        result = PlainTextParser().parse(path)
        assert result.text == ""
        assert result.char_count == 0


class TestMarkdownParser:
    def test_preserves_markdown(self, write_file):
        content = "# Title\n\nParagraph with **bold** and [link](http://x).\n"
        path = write_file("a.md", content)
        result = MarkdownParser().parse(path)
        assert result.text == content
        assert result.parser_name == "markdown"


class TestCSVParser:
    def test_basic(self, write_file):
        content = "name,age\nAna,30\nBob,25\n"
        path = write_file("a.csv", content)
        result = CSVParser().parse(path)
        assert "name: Ana | age: 30" in result.text
        assert "name: Bob | age: 25" in result.text
        assert result.metadata == {"rows": "2", "columns": "2"}

    def test_preserves_pt_chars(self, write_file):
        content = "produto,descrição\ncafé,bebida quente\n"
        path = write_file("a.csv", content)
        result = CSVParser().parse(path)
        assert "produto: café | descrição: bebida quente" in result.text

    def test_empty_csv_raises(self, write_file):
        path = write_file("a.csv", "")
        with pytest.raises(ParserError, match="without header"):
            CSVParser().parse(path)


class TestJSONParser:
    def test_object(self, write_file):
        # Sample with PT content to confirm ensure_ascii=False preserves accents.
        obj = {"nome": "Ação", "items": [1, 2, 3]}
        path = write_file("a.json", json.dumps(obj))
        result = JSONParser().parse(path)
        assert "Ação" in result.text
        assert '"items"' in result.text
        # Indentation applied
        assert "  " in result.text

    def test_array(self, write_file):
        path = write_file("a.json", json.dumps([{"a": 1}, {"b": 2}]))
        result = JSONParser().parse(path)
        assert result.text.startswith("[")
        assert result.text.endswith("]")

    def test_invalid_raises(self, write_file):
        path = write_file("bad.json", "{not json")
        with pytest.raises(ParserError, match="invalid JSON"):
            JSONParser().parse(path)
