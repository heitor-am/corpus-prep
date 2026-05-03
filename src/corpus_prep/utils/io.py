"""I/O helpers shared between parsers."""

from __future__ import annotations

from pathlib import Path


def read_text_with_fallback(path: Path) -> str:
    """Read a text file as UTF-8, falling back to Latin-1 on decode errors.

    Latin-1 decodes any byte without raising — any mojibake produced this way
    is recoverable downstream via ftfy in the normalize stage.
    """
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")
