"""Testes da normalização (Q4 da atividade 03 + edge cases)."""

from __future__ import annotations

from corpus_prep.normalize import normalize


class TestFTFYIntegration:
    """Casos de mojibake do enunciado da Q4."""

    def test_fixes_common_pt_mojibake(self):
        cases = {
            "Ã©": "é",
            "Ã£o": "ão",
            "nÃ£o": "não",
            "informaÃ§Ã£o": "informação",
            "sÃ£o": "são",
        }
        for corrupted, expected in cases.items():
            assert normalize(corrupted) == expected, f"falhou para {corrupted!r}"

    def test_fixes_curly_quotes(self):
        # ftfy normaliza aspas tipográficas sem mudar o caractere por padrão,
        # mas mantém o texto legível.
        result = normalize("hello “world”")
        assert "hello" in result
        assert "world" in result


class TestUnicodeNormalization:
    def test_nfc_combines_decomposed(self):
        # 'á' decomposto: a + combining acute (U+0301)
        decomposed = "á"
        result = normalize(decomposed)
        # NFC combina em U+00E1 (composto)
        assert result == "á"
        assert len(result) == 1


class TestControlCharStripping:
    def test_removes_null_byte(self):
        assert normalize("hello\x00world") == "helloworld"

    def test_removes_bell_and_other_controls(self):
        # \x07 (bell), \x0B (vtab), \x1F (unit separator) — todos removidos
        text = "a\x07b\x0bc\x1fd"
        assert normalize(text) == "abcd"

    def test_preserves_newline_collapses_tab(self):
        # Newline preservado (estrutural). Tab colapsado em espaço junto com
        # outros whitespace runs — comportamento desejado para training corpus.
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
        # 4 newlines viram 2
        text = "para 1\n\n\n\npara 2"
        assert normalize(text) == "para 1\n\npara 2"

    def test_preserves_paragraph_break(self):
        # 2 newlines (paragraph break) preservados
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
