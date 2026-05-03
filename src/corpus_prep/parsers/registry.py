"""Registry pattern para roteamento de parsers por MIME type."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from corpus_prep.parsers.base import BaseParser, UnsupportedFormatError

_registry: dict[str, type[BaseParser]] = {}


def register(*mime_types: str) -> Callable[[type[BaseParser]], type[BaseParser]]:
    """Decorator que registra um parser para os MIME types informados.

    Exemplo:
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
    """Retorna uma instância do parser registrado para `mime`.

    Args:
        mime: MIME type (ex.: 'text/plain').
        source: Path opcional; usado apenas para enriquecer o erro.

    Raises:
        UnsupportedFormatError: se nenhum parser estiver registrado.
    """
    cls = _registry.get(mime)
    if cls is None:
        raise UnsupportedFormatError(source or Path("<unknown>"), mime)
    return cls()


def list_supported_mimes() -> list[str]:
    """Retorna os MIME types registrados, ordenados."""
    return sorted(_registry.keys())


def is_supported(mime: str) -> bool:
    """Conveniência: existe parser registrado para `mime`?"""
    return mime in _registry


def _reset_registry_for_tests() -> None:
    """Apenas para testes — limpa o registry global."""
    _registry.clear()
