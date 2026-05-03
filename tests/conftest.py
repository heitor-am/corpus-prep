"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def write_file(tmp_path: Path):
    """Helper for creating temp files with given content.

    Usage:
        path = write_file("test.txt", "content", encoding="utf-8")
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
    """Create a PDF with a real text layer using ReportLab."""
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
    """Create a PDF with no extractable text (just a geometric shape).

    Simulates a scanned PDF: PyMuPDF4LLM extracts zero text, triggering
    needs_ocr=true.
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
