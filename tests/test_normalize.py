"""Tests for the normalization pipeline."""

from __future__ import annotations

from corpus_prep.normalize import normalize


class TestFTFYIntegration:
    """Common mojibake patterns and their expected repairs."""

    def test_fixes_common_pt_mojibake(self):
        # Inputs are deliberately corrupted PT samples to exercise ftfy.
        cases = {
            "Ã©": "é",
            "Ã£o": "ão",
            "nÃ£o": "não",
            "informaÃ§Ã£o": "informação",
            "sÃ£o": "são",
        }
        for corrupted, expected in cases.items():
            assert normalize(corrupted) == expected, f"failed for {corrupted!r}"

    def test_fixes_curly_quotes(self):
        # ftfy keeps typographic quotes by default but the text remains readable.
        result = normalize("hello “world”")
        assert "hello" in result
        assert "world" in result


class TestUnicodeNormalization:
    def test_nfc_combines_decomposed(self):
        # 'á' decomposed: a + combining acute (U+0301).
        decomposed = "á"
        result = normalize(decomposed)
        # NFC composes into U+00E1.
        assert result == "á"
        assert len(result) == 1


class TestControlCharStripping:
    def test_removes_null_byte(self):
        assert normalize("hello\x00world") == "helloworld"

    def test_removes_bell_and_other_controls(self):
        # \x07 (bell), \x0B (vtab), \x1F (unit separator) all removed.
        text = "a\x07b\x0bc\x1fd"
        assert normalize(text) == "abcd"

    def test_preserves_newline_collapses_tab(self):
        # Newlines stay (structural). Tabs collapse into a space alongside other
        # whitespace runs — desired behavior for a training corpus.
        text = "linha 1\nlinha 2\tcoluna"
        result = normalize(text)
        assert "\n" in result
        assert "\t" not in result
        assert "linha 2 coluna" in result


class TestWhitespaceCollapse:
    def test_collapses_multiple_spaces(self):
        assert normalize("foo    bar") == "foo bar"

    def test_collapses_mixed_tabs_and_spaces(self):
        assert normalize("foo \t  bar") == "foo bar"

    def test_collapses_excess_newlines(self):
        # 4 newlines collapse to 2.
        text = "para 1\n\n\n\npara 2"
        assert normalize(text) == "para 1\n\npara 2"

    def test_preserves_paragraph_break(self):
        # A double newline (paragraph break) is preserved.
        text = "para 1\n\npara 2"
        assert normalize(text) == "para 1\n\npara 2"

    def test_strips_edges(self):
        assert normalize("  \n  hello  \n  ") == "hello"


class TestEdgeCases:
    def test_empty_string(self):
        assert normalize("") == ""

    def test_whitespace_only(self):
        assert normalize("   \n\t  ") == ""

    def test_idempotent(self):
        text = "Olá mundo, ção é fácil!"
        assert normalize(normalize(text)) == normalize(text)
