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
