"""Interface base para parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from corpus_prep.schemas import ParseResult


class ParserError(Exception):
    """Falha durante parsing. Inclui o path para diagnóstico."""

    def __init__(self, path: Path, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path


class UnsupportedFormatError(ParserError):
    """MIME type não tem parser registrado."""

    def __init__(self, path: Path, mime: str) -> None:
        super().__init__(path, f"unsupported MIME type: {mime}")
        self.mime = mime


class BaseParser(ABC):
    """Contrato para todos os parsers do registry.

    Parsers são síncronos e não-stateful — instâncias podem ser descartadas após uso.
    Concorrência fica a cargo do orquestrador (ProcessPoolExecutor).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Identificador estável do parser. Vai parar no campo `parser` do Document."""

    @property
    @abstractmethod
    def supported_mime_types(self) -> list[str]:
        """MIME types que este parser declara suportar."""

    @abstractmethod
    def parse(self, path: Path) -> ParseResult:
        """Lê o arquivo em `path` e retorna o ParseResult.

        Raises:
            ParserError: se o arquivo não puder ser processado.
        """
