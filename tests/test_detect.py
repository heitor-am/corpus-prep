"""Tests for the Magika-based MIME detection."""

from __future__ import annotations

import pytest

from corpus_prep.detect import (
    FALLBACK_MIME,
    _reset_cache_for_tests,
    detect_mime,
    detect_with_score,
)


@pytest.fixture(autouse=True)
def _reset_magika_cache():
    """Ensure a clean singleton between tests."""
    _reset_cache_for_tests()
    yield
    _reset_cache_for_tests()


class TestDetectMime:
    def test_detects_pdf(self, make_native_pdf):
        path = make_native_pdf(text="Hello world testing detection.")
        mime = detect_mime(path)
        assert mime == "application/pdf"

    def test_detects_plaintext(self, write_file):
        path = write_file("a.txt", "this is just plain ascii text content")
        mime = detect_mime(path)
        assert mime in {"text/plain", "text/x-tex", "text/x-asm"}  # Magika is conservative

    def test_detects_json(self, write_file):
        path = write_file("a.json", '{"key": "value", "n": 42}')
        mime = detect_mime(path)
        assert mime == "application/json"

    def test_detects_html(self, write_file):
        html = (
            "<!DOCTYPE html><html><head><title>x</title></head>"
            "<body><h1>Test</h1><p>Content</p></body></html>"
        )
        path = write_file("a.html", html)
        mime = detect_mime(path)
        assert mime == "text/html"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            detect_mime(tmp_path / "nope.txt")


class TestDetectWithScore:
    def test_returns_tuple(self, write_file):
        path = write_file("a.json", '{"key": "value"}')
        mime, score = detect_with_score(path)
        assert isinstance(mime, str)
        assert 0.0 <= score <= 1.0

    def test_high_confidence_for_obvious_format(self, make_native_pdf):
        path = make_native_pdf()
        _, score = detect_with_score(path)
        assert score > 0.9


class TestThreshold:
    def test_low_threshold_returns_native_mime(self, write_file):
        # Zero threshold lets any detection through.
        path = write_file("a.json", '{"x": 1}')
        mime = detect_mime(path, min_confidence=0.0)
        assert mime != FALLBACK_MIME

    def test_high_threshold_can_force_fallback(self, write_file):
        # Absurd threshold (1.1) always forces fallback.
        path = write_file("a.json", '{"x": 1}')
        mime = detect_mime(path, min_confidence=1.1)
        assert mime == FALLBACK_MIME
