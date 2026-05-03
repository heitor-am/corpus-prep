"""I/O helpers compartilhados entre parsers."""

from __future__ import annotations

from pathlib import Path


def read_text_with_fallback(path: Path) -> str:
    """Lê arquivo de texto tentando UTF-8 e caindo para Latin-1.

    Latin-1 decodifica qualquer byte sem levantar — encoding-fix posterior
    via ftfy consegue recuperar mojibake gerado por essa estratégia.
    """
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")
