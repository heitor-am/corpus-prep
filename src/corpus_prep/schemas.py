"""Pydantic models for the extraction pipeline.

Full spec in PRD.md section 8. This M1 cut only includes ParseResult and
Document. FilterStats, RunReport and ShardManifest land in M4-M5.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ParseResult(BaseModel):
    """Output of a single parser invocation on one file."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(description="Extracted text (raw, before normalization).")
    parser_name: str = Field(description="Name of the parser that produced this result.")
    char_count: int = Field(ge=0, description="Character count of text.")
    page_count: int | None = Field(
        default=None, ge=0, description="Pages or slides when applicable."
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Parser-specific metadata. Values must be str for Parquet output.",
    )


class Document(BaseModel):
    """Canonical corpus entity, ready to be written to Parquet."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: UUID = Field(description="UUIDv7 sortable by extraction timestamp.")
    text: str = Field(description="Normalized text ready for the corpus.")
    source_path: Path = Field(description="Original path (relative to input dir).")
    mime: str = Field(description="MIME type detected by Magika.")
    parser: str = Field(description="Name of the parser used.")
    sha256: str = Field(
        min_length=64, max_length=64, description="SHA-256 of the original binary."
    )
    char_count: int = Field(ge=0)
    extracted_at: datetime
    language: str | None = Field(
        default=None, description="GlotLID label (e.g. 'por_Latn')."
    )
    language_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, str] = Field(default_factory=dict)
