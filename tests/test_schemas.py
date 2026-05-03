"""Testes dos schemas Pydantic e do helper uuid7."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from corpus_prep.schemas import Document, ParseResult
from corpus_prep.utils.ids import uuid7


class TestParseResult:
    def test_minimal(self):
        result = ParseResult(text="oi", parser_name="x", char_count=2)
        assert result.text == "oi"
        assert result.page_count is None
        assert result.metadata == {}

    def test_frozen(self):
        result = ParseResult(text="oi", parser_name="x", char_count=2)
        with pytest.raises(ValidationError):
            result.text = "outro"  # type: ignore[misc]

    def test_negative_char_count_rejected(self):
        with pytest.raises(ValidationError):
            ParseResult(text="oi", parser_name="x", char_count=-1)


class TestDocument:
    def _make(self, **overrides):
        defaults = {
            "id": uuid7(),
            "text": "olá mundo",
            "source_path": Path("a/b.txt"),
            "mime": "text/plain",
            "parser": "plaintext",
            "sha256": "a" * 64,
            "char_count": 9,
            "extracted_at": datetime.now(timezone.utc),
        }
        return Document(**(defaults | overrides))

    def test_minimal(self):
        doc = self._make()
        assert doc.language is None
        assert doc.metadata == {}

    def test_sha256_length_enforced(self):
        with pytest.raises(ValidationError):
            self._make(sha256="abc")

    def test_language_confidence_bounded(self):
        with pytest.raises(ValidationError):
            self._make(language="por_Latn", language_confidence=1.5)


class TestUUID7:
    def test_version_bits(self):
        u = uuid7()
        assert u.version == 7

    def test_variant_bits(self):
        u = uuid7()
        assert u.variant == "specified in RFC 4122"

    def test_sortable_by_creation(self):
        first = uuid7()
        time.sleep(0.005)
        second = uuid7()
        assert first.int < second.int
