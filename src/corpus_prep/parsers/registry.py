"""Registry pattern for routing parsers by MIME type."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from corpus_prep.parsers.base import BaseParser, UnsupportedFormatError

_registry: dict[str, type[BaseParser]] = {}


def register(*mime_types: str) -> Callable[[type[BaseParser]], type[BaseParser]]:
    """Decorator that registers a parser for the given MIME types.

    Example:
        @register("text/plain")
        class PlainTextParser(BaseParser): ...
    """
    if not mime_types:
        raise ValueError("register() requires at least one mime type")

    def decorator(cls: type[BaseParser]) -> type[BaseParser]:
        for mime in mime_types:
            _registry[mime] = cls
        return cls

    return decorator


def get_parser(mime: str, *, source: Path | None = None) -> BaseParser:
    """Return an instance of the parser registered for ``mime``.

    Args:
        mime: MIME type (e.g. ``text/plain``).
        source: Optional path used only to enrich the error.

    Raises:
        UnsupportedFormatError: when no parser is registered for ``mime``.
    """
    cls = _registry.get(mime)
    if cls is None:
        raise UnsupportedFormatError(source or Path("<unknown>"), mime)
    return cls()


def list_supported_mimes() -> list[str]:
    """Return the registered MIME types, sorted."""
    return sorted(_registry.keys())


def is_supported(mime: str) -> bool:
    """Convenience: is there a parser registered for ``mime``?"""
    return mime in _registry


def _reset_registry_for_tests() -> None:
    """Test-only helper to clear the global registry."""
    _registry.clear()
