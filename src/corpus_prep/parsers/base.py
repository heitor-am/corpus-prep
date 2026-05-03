"""Base interface for parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from corpus_prep.schemas import ParseResult


class ParserError(Exception):
    """Raised when parsing fails. Includes the path for diagnostics."""

    def __init__(self, path: Path, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path


class UnsupportedFormatError(ParserError):
    """No parser is registered for the given MIME type."""

    def __init__(self, path: Path, mime: str) -> None:
        super().__init__(path, f"unsupported MIME type: {mime}")
        self.mime = mime


class BaseParser(ABC):
    """Contract for every parser in the registry.

    Parsers are synchronous and stateless — instances are disposable after a
    single parse call. Concurrency is the orchestrator's job
    (ProcessPoolExecutor in pipeline.py).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier of the parser. Stored on the Document.parser field."""

    @property
    @abstractmethod
    def supported_mime_types(self) -> list[str]:
        """MIME types this parser declares support for."""

    @abstractmethod
    def parse(self, path: Path) -> ParseResult:
        """Read the file at ``path`` and return a ParseResult.

        Raises:
            ParserError: when the file cannot be processed.
        """
