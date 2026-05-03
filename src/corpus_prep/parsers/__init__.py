"""Parsers package — auto-imports each module so the global registry gets populated."""

from corpus_prep.parsers import (  # noqa: F401
    docling_parser,
    html_parser,
    pdf_native,
    textlike,
)
from corpus_prep.parsers.base import BaseParser, ParserError, UnsupportedFormatError
from corpus_prep.parsers.registry import (
    get_parser,
    is_supported,
    list_supported_mimes,
    register,
)

__all__ = [
    "BaseParser",
    "ParserError",
    "UnsupportedFormatError",
    "get_parser",
    "is_supported",
    "list_supported_mimes",
    "register",
]
