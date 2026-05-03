"""Tests for the HTMLParser (Trafilatura)."""

from __future__ import annotations

import pytest

from corpus_prep.parsers.base import ParserError
from corpus_prep.parsers.html_parser import HTMLParser

# Sample data deliberately in PT to validate UTF-8 handling end-to-end.
SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>Notícia</title></head>
<body>
  <nav>Menu | Home | Contato</nav>
  <article>
    <h1>Título da matéria</h1>
    <p>Primeiro parágrafo com conteúdo principal relevante para o leitor.</p>
    <p>Segundo parágrafo continua a narrativa principal da matéria.</p>
  </article>
  <footer>Copyright 2026 - Todos os direitos reservados</footer>
  <aside>Anúncios e links patrocinados aqui.</aside>
</body>
</html>
"""


class TestHTMLParser:
    def test_extracts_main_content(self, write_file):
        path = write_file("page.html", SAMPLE_HTML)
        result = HTMLParser().parse(path)

        assert result.parser_name == "html"
        assert "conteúdo principal" in result.text
        assert "narrativa principal" in result.text

    def test_removes_boilerplate(self, write_file):
        """Trafilatura should drop nav/footer/aside under default settings."""
        path = write_file("page.html", SAMPLE_HTML)
        result = HTMLParser().parse(path)

        assert "Anúncios" not in result.text
        assert "Copyright" not in result.text
        assert "Menu | Home" not in result.text

    def test_includes_tables(self, write_file):
        html = """<html><body><article>
        <h1>Test</h1>
        <p>Intro paragraph providing some context.</p>
        <table>
          <tr><th>Col1</th><th>Col2</th></tr>
          <tr><td>val1</td><td>val2</td></tr>
        </table>
        </article></body></html>"""
        path = write_file("table.html", html)
        result = HTMLParser().parse(path)
        # include_tables=True must preserve a cell value.
        assert "val1" in result.text or "val2" in result.text

    def test_empty_html_raises(self, write_file):
        path = write_file("empty.html", "<html></html>")
        with pytest.raises(ParserError, match="extract"):
            HTMLParser().parse(path)

    def test_supported_mime_types(self):
        parser = HTMLParser()
        assert parser.supported_mime_types == ["text/html"]
        assert parser.name == "html"
