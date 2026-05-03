"""Tests for the Registry pattern."""

from __future__ import annotations

from pathlib import Path

import pytest

from corpus_prep.parsers.base import BaseParser, UnsupportedFormatError
from corpus_prep.parsers.registry import (
    _reset_registry_for_tests,
    get_parser,
    is_supported,
    list_supported_mimes,
    register,
)
from corpus_prep.schemas import ParseResult


@pytest.fixture
def clean_registry():
    """Isolate each test with an empty registry, restoring all default parsers afterwards."""
    _reset_registry_for_tests()
    yield
    _reset_registry_for_tests()
    import importlib

    from corpus_prep.parsers import (
        docling_parser,
        html_parser,
        pdf_native,
        textlike,
    )

    for module in [textlike, html_parser, pdf_native, docling_parser]:
        importlib.reload(module)


class _DummyParser(BaseParser):
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/x-dummy"]

    def parse(self, path: Path) -> ParseResult:
        return ParseResult(text="dummy", parser_name=self.name, char_count=5)


class TestRegister:
    def test_register_and_lookup(self, clean_registry):
        register("application/x-dummy")(_DummyParser)
        parser = get_parser("application/x-dummy")
        assert isinstance(parser, _DummyParser)

    def test_register_multiple_mimes(self, clean_registry):
        register("application/x-dummy", "application/x-dummy2")(_DummyParser)
        assert isinstance(get_parser("application/x-dummy"), _DummyParser)
        assert isinstance(get_parser("application/x-dummy2"), _DummyParser)

    def test_register_requires_mime(self, clean_registry):
        with pytest.raises(ValueError, match="at least one mime type"):
            register()(_DummyParser)

    def test_unknown_mime_raises(self, clean_registry):
        with pytest.raises(UnsupportedFormatError) as excinfo:
            get_parser("application/x-unknown")
        assert excinfo.value.mime == "application/x-unknown"

    def test_unknown_mime_includes_path(self, clean_registry):
        with pytest.raises(UnsupportedFormatError) as excinfo:
            get_parser("application/x-unknown", source=Path("foo.bin"))
        assert excinfo.value.path == Path("foo.bin")

    def test_list_supported_mimes_sorted(self, clean_registry):
        register("z/dummy", "a/dummy")(_DummyParser)
        assert list_supported_mimes() == ["a/dummy", "z/dummy"]

    def test_is_supported(self, clean_registry):
        register("application/x-dummy")(_DummyParser)
        assert is_supported("application/x-dummy") is True
        assert is_supported("application/x-other") is False


class TestDefaultRegistration:
    """Sanity check: default parsers register themselves on import."""

    def test_textlike_parsers_registered(self):
        from corpus_prep import parsers  # noqa: F401

        for mime in ["text/plain", "text/markdown", "text/csv", "application/json"]:
            assert is_supported(mime), f"{mime} should be registered"

    def test_pdf_and_html_registered(self):
        from corpus_prep import parsers  # noqa: F401

        for mime in ["application/pdf", "text/html"]:
            assert is_supported(mime), f"{mime} should be registered"

    def test_docling_office_and_image_registered(self):
        from corpus_prep import parsers  # noqa: F401

        for mime in [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "image/png",
            "image/jpeg",
            "image/tiff",
        ]:
            assert is_supported(mime), f"{mime} should be registered"
