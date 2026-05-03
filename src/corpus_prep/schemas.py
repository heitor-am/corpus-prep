"""Pydantic models para o pipeline de extração.

Spec completa em PRD.md §8. Esta versão (M1) inclui apenas ParseResult e Document.
Schemas adicionais (FilterStats, RunReport, ShardManifest) virão nos milestones 4-5.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ParseResult(BaseModel):
    """Output de um parser sobre um único arquivo."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(description="Texto extraído (cru, antes de normalização).")
    parser_name: str = Field(description="Nome do parser que gerou este resultado.")
    char_count: int = Field(ge=0, description="Contagem de caracteres em text.")
    page_count: int | None = Field(
        default=None, ge=0, description="Páginas/slides quando aplicável."
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Metadados específicos do parser. Valores sempre como str para Parquet.",
    )


class Document(BaseModel):
    """Entidade canônica do corpus, pronta para ser escrita em Parquet."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: UUID = Field(description="UUIDv7 sortable por timestamp de extração.")
    text: str = Field(description="Texto normalizado e pronto para o corpus.")
    source_path: Path = Field(description="Path original (relativo ao input dir).")
    mime: str = Field(description="MIME type detectado por Magika.")
    parser: str = Field(description="Nome do parser usado.")
    sha256: str = Field(
        min_length=64, max_length=64, description="SHA-256 do arquivo original."
    )
    char_count: int = Field(ge=0)
    extracted_at: datetime
    language: str | None = Field(
        default=None, description="Código GlotLID (ex.: 'por_Latn')."
    )
    language_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, str] = Field(default_factory=dict)
