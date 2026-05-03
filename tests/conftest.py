"""Fixtures compartilhadas entre os testes."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def write_file(tmp_path: Path):
    """Helper para criar arquivos temporários com conteúdo dado.

    Uso:
        path = write_file("teste.txt", "conteúdo", encoding="utf-8")
    """

    def _write(name: str, content: str | bytes, encoding: str = "utf-8") -> Path:
        path = tmp_path / name
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding=encoding)
        return path

    return _write


@pytest.fixture
def make_native_pdf(tmp_path: Path):
    """Cria um PDF com camada de texto usando ReportLab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    def _make(name: str = "native.pdf", text: str = "Hello world.\nLine two.") -> Path:
        path = tmp_path / name
        c = canvas.Canvas(str(path), pagesize=A4)
        c.setFont("Helvetica", 12)
        y = 800
        for line in text.split("\n"):
            c.drawString(50, y, line)
            y -= 20
        c.showPage()
        c.save()
        return path

    return _make


@pytest.fixture
def make_blank_pdf(tmp_path: Path):
    """Cria um PDF sem texto extraível (só uma forma geométrica).

    Simula PDF escaneado: PyMuPDF4LLM extrai zero texto, disparando needs_ocr=true.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    def _make(name: str = "blank.pdf") -> Path:
        path = tmp_path / name
        c = canvas.Canvas(str(path), pagesize=A4)
        c.rect(50, 50, 500, 700, stroke=1, fill=0)
        c.showPage()
        c.save()
        return path

    return _make
