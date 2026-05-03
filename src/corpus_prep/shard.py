"""Parquet sharding for the corpus output.

Schema spec lives in PRD section 7.6. Output layout:

    output_dir/
        shard-0000.parquet
        shard-0001.parquet
        ...
        manifest.json

The manifest carries enough information for downstream consumers
(``datasets.load_dataset("parquet", data_files="output_dir/shard-*.parquet")``,
DuckDB, hand-written readers) to reconstruct the run context without parsing
each shard.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from corpus_prep.schemas import Document

SCHEMA_VERSION = "1.0"
DEFAULT_MAX_DOCS_PER_SHARD = 10_000
DEFAULT_COMPRESSION = "zstd"
DEFAULT_COMPRESSION_LEVEL = 3
MANIFEST_FILENAME = "manifest.json"


PARQUET_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string(), nullable=False),
        pa.field("text", pa.large_string(), nullable=False),
        pa.field("source_path", pa.string(), nullable=False),
        pa.field("mime", pa.string(), nullable=False),
        pa.field("parser", pa.string(), nullable=False),
        pa.field("extracted_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("char_count", pa.int32(), nullable=False),
        pa.field("language", pa.string(), nullable=True),
        pa.field("language_confidence", pa.float32(), nullable=True),
        pa.field("sha256", pa.string(), nullable=False),
        pa.field("metadata", pa.map_(pa.string(), pa.string()), nullable=False),
    ]
)


@dataclass
class ShardInfo:
    """Per-shard metadata recorded in the manifest."""

    path: str  # relative to output_dir
    document_count: int
    byte_size: int
    sha256: str  # of the .parquet file


@dataclass
class ShardManifest:
    """Per-run output manifest (manifest.json)."""

    schema_version: str
    created_at: datetime
    total_documents: int
    total_chars: int
    shards: list[ShardInfo] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at.isoformat(),
            "total_documents": self.total_documents,
            "total_chars": self.total_chars,
            "shards": [
                {
                    "path": s.path,
                    "document_count": s.document_count,
                    "byte_size": s.byte_size,
                    "sha256": s.sha256,
                }
                for s in self.shards
            ],
            "config": self.config,
        }


def docs_to_table(docs: Iterable[Document]) -> pa.Table:
    """Convert Documents to a pyarrow.Table conforming to ``PARQUET_SCHEMA``.

    Materializes the iterable into memory — fine at shard granularity (~10k docs)
    but not for full-corpus calls; use :class:`ShardWriter` for streaming.
    """
    rows = list(docs)
    return pa.table(
        {
            "id": [str(d.id) for d in rows],
            "text": [d.text for d in rows],
            "source_path": [str(d.source_path) for d in rows],
            "mime": [d.mime for d in rows],
            "parser": [d.parser for d in rows],
            "extracted_at": [
                d.extracted_at.astimezone(UTC) for d in rows
            ],
            "char_count": [d.char_count for d in rows],
            "language": [d.language for d in rows],
            "language_confidence": [d.language_confidence for d in rows],
            "sha256": [d.sha256 for d in rows],
            "metadata": [list(d.metadata.items()) for d in rows],
        },
        schema=PARQUET_SCHEMA,
    )


def _file_sha256(path: Path, *, chunk_size: int = 64 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


class ShardWriter:
    """Buffer Documents and rotate to a new Parquet shard at the threshold.

    Usage:
        with ShardWriter(output_dir) as writer:
            for doc in docs:
                writer.write(doc)
        manifest = writer.manifest  # populated on close()

    Rotation is by document count rather than byte size — predictable and
    easier to reason about than estimating compressed sizes mid-stream.
    """

    def __init__(
        self,
        output_dir: Path,
        *,
        max_docs_per_shard: int = DEFAULT_MAX_DOCS_PER_SHARD,
        compression: str = DEFAULT_COMPRESSION,
        compression_level: int = DEFAULT_COMPRESSION_LEVEL,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.max_docs_per_shard = max_docs_per_shard
        self.compression = compression
        self.compression_level = compression_level
        self.config = config or {}

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._buffer: list[Document] = []
        self._shard_index = 0
        self._shards: list[ShardInfo] = []
        self._total_documents = 0
        self._total_chars = 0
        self.manifest: ShardManifest | None = None

    def write(self, doc: Document) -> None:
        """Add ``doc`` to the buffer; flush if the threshold is reached."""
        self._buffer.append(doc)
        if len(self._buffer) >= self.max_docs_per_shard:
            self._flush()

    def write_many(self, docs: Iterable[Document]) -> None:
        for doc in docs:
            self.write(doc)

    def close(self) -> ShardManifest:
        """Flush remaining buffer, write the manifest JSON, and return it."""
        if self._buffer:
            self._flush()
        self.manifest = ShardManifest(
            schema_version=SCHEMA_VERSION,
            created_at=datetime.now(UTC),
            total_documents=self._total_documents,
            total_chars=self._total_chars,
            shards=self._shards,
            config=self.config,
        )
        manifest_path = self.output_dir / MANIFEST_FILENAME
        manifest_path.write_text(
            json.dumps(self.manifest.to_dict(), indent=2, ensure_ascii=False)
        )
        return self.manifest

    def __enter__(self) -> ShardWriter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # ------------------------------ internals ------------------------------

    def _flush(self) -> None:
        if not self._buffer:
            return
        shard_name = f"shard-{self._shard_index:04d}.parquet"
        shard_path = self.output_dir / shard_name

        table = docs_to_table(self._buffer)
        pq.write_table(  # type: ignore[no-untyped-call]
            table,
            shard_path,
            compression=self.compression,
            compression_level=self.compression_level,
        )

        chars_in_shard = sum(d.char_count for d in self._buffer)
        self._total_documents += len(self._buffer)
        self._total_chars += chars_in_shard

        self._shards.append(
            ShardInfo(
                path=shard_name,
                document_count=len(self._buffer),
                byte_size=shard_path.stat().st_size,
                sha256=_file_sha256(shard_path),
            )
        )
        self._shard_index += 1
        self._buffer.clear()


def write_shards(
    docs: Iterable[Document],
    output_dir: Path,
    *,
    max_docs_per_shard: int = DEFAULT_MAX_DOCS_PER_SHARD,
    compression: str = DEFAULT_COMPRESSION,
    compression_level: int = DEFAULT_COMPRESSION_LEVEL,
    config: dict[str, Any] | None = None,
) -> ShardManifest:
    """One-shot convenience wrapper around :class:`ShardWriter`."""
    with ShardWriter(
        output_dir,
        max_docs_per_shard=max_docs_per_shard,
        compression=compression,
        compression_level=compression_level,
        config=config,
    ) as writer:
        writer.write_many(docs)
    assert writer.manifest is not None  # always set by close()
    return writer.manifest
