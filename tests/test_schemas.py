"""Tests for the Pydantic schemas and the uuid7 helper."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from corpus_prep.schemas import Document, ParseResult
from corpus_prep.utils.ids import uuid7


class TestParseResult:
    def test_minimal(self):
        result = ParseResult(text="hi", parser_name="x", char_count=2)
        assert result.text == "hi"
        assert result.page_count is None
        assert result.metadata == {}

    def test_frozen(self):
        result = ParseResult(text="hi", parser_name="x", char_count=2)
        with pytest.raises(ValidationError):
            result.text = "other"  # type: ignore[misc]

    def test_negative_char_count_rejected(self):
        with pytest.raises(ValidationError):
            ParseResult(text="hi", parser_name="x", char_count=-1)


class TestDocument:
    def _make(self, **overrides):
        defaults = {
            "id": uuid7(),
            "text": "hello world",
            "source_path": Path("a/b.txt"),
            "mime": "text/plain",
            "parser": "plaintext",
            "sha256": "a" * 64,
            "char_count": 11,
            "extracted_at": datetime.now(UTC),
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
