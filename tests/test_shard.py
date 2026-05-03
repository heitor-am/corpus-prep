"""Tests for the Parquet sharding output."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq

from corpus_prep.schemas import Document
from corpus_prep.shard import (
    MANIFEST_FILENAME,
    PARQUET_SCHEMA,
    SCHEMA_VERSION,
    ShardWriter,
    docs_to_table,
    write_shards,
)
from corpus_prep.utils.ids import uuid7


def _doc(text: str, **overrides) -> Document:
    defaults = {
        "id": uuid7(),
        "text": text,
        "source_path": Path("input/x.txt"),
        "mime": "text/plain",
        "parser": "plaintext",
        "sha256": "a" * 64,
        "char_count": len(text),
        "extracted_at": datetime.now(UTC),
        "language": "por_Latn",
        "language_confidence": 0.97,
        "metadata": {"key": "value"},
    }
    return Document(**(defaults | overrides))


# ----------------------------- docs_to_table -------------------------------


class TestDocsToTable:
    def test_schema_matches(self):
        table = docs_to_table([_doc("hello"), _doc("world")])
        assert table.schema.equals(PARQUET_SCHEMA)
        assert table.num_rows == 2

    def test_round_trip_through_parquet(self, tmp_path):
        original = [_doc("hello world"), _doc("second doc with more text")]
        path = tmp_path / "shard.parquet"
        pq.write_table(docs_to_table(original), path, compression="zstd")
        loaded = pq.read_table(path)

        assert loaded.num_rows == len(original)
        assert loaded["text"].to_pylist() == [d.text for d in original]
        assert loaded["language"].to_pylist() == [d.language for d in original]

    def test_metadata_map_preserved(self, tmp_path):
        doc = _doc("x", metadata={"a": "1", "b": "2"})
        path = tmp_path / "shard.parquet"
        pq.write_table(docs_to_table([doc]), path)
        loaded = pq.read_table(path)
        # pyarrow returns the map as a list of (k, v) pairs; reassemble.
        meta = dict(loaded["metadata"][0].as_py())
        assert meta == {"a": "1", "b": "2"}


# ----------------------------- ShardWriter ---------------------------------


class TestShardWriter:
    def test_single_shard_below_threshold(self, tmp_path):
        with ShardWriter(tmp_path, max_docs_per_shard=10) as writer:
            for i in range(3):
                writer.write(_doc(f"doc {i}"))

        assert writer.manifest is not None
        assert len(writer.manifest.shards) == 1
        assert writer.manifest.shards[0].path == "shard-0000.parquet"
        assert writer.manifest.shards[0].document_count == 3
        assert writer.manifest.total_documents == 3

    def test_rotation_at_threshold(self, tmp_path):
        with ShardWriter(tmp_path, max_docs_per_shard=2) as writer:
            for i in range(5):
                writer.write(_doc(f"doc {i}"))

        manifest = writer.manifest
        assert manifest is not None
        # 5 docs / 2 per shard -> 3 shards (2, 2, 1)
        assert len(manifest.shards) == 3
        names = [s.path for s in manifest.shards]
        assert names == [
            "shard-0000.parquet",
            "shard-0001.parquet",
            "shard-0002.parquet",
        ]
        assert [s.document_count for s in manifest.shards] == [2, 2, 1]

    def test_writes_manifest_json(self, tmp_path):
        with ShardWriter(tmp_path) as writer:
            writer.write(_doc("only doc"))

        manifest_path = tmp_path / MANIFEST_FILENAME
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text())
        assert data["schema_version"] == SCHEMA_VERSION
        assert data["total_documents"] == 1
        assert len(data["shards"]) == 1

    def test_empty_writer(self, tmp_path):
        with ShardWriter(tmp_path) as writer:
            pass  # nothing written

        manifest = writer.manifest
        assert manifest is not None
        assert manifest.total_documents == 0
        assert manifest.shards == []
        # manifest.json still gets written.
        assert (tmp_path / MANIFEST_FILENAME).exists()

    def test_config_stored_in_manifest(self, tmp_path):
        cfg = {"dedup_threshold": 0.8, "enable_filter": True}
        with ShardWriter(tmp_path, config=cfg) as writer:
            writer.write(_doc("x"))

        data = json.loads((tmp_path / MANIFEST_FILENAME).read_text())
        assert data["config"] == cfg

    def test_shard_sha256_recorded(self, tmp_path):
        with ShardWriter(tmp_path) as writer:
            writer.write(_doc("hello"))

        info = writer.manifest.shards[0]  # type: ignore[union-attr]
        assert len(info.sha256) == 64
        assert info.byte_size > 0


# ----------------------------- write_shards convenience -------------------


class TestWriteShards:
    def test_one_shot(self, tmp_path):
        docs = [_doc(f"doc {i}") for i in range(5)]
        manifest = write_shards(docs, tmp_path, max_docs_per_shard=3)

        assert manifest.total_documents == 5
        assert len(manifest.shards) == 2
        # Reads back via parquet to confirm shape.
        table = pq.read_table(tmp_path / "shard-0000.parquet")
        assert table.num_rows == 3
