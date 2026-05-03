"""Tests for the deduplication module."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from corpus_prep.dedup import (
    dedup_documents,
    dedup_files,
    file_sha256,
    make_minhash,
)
from corpus_prep.schemas import Document
from corpus_prep.utils.ids import uuid7


def _doc(text: str, sha: str | None = None) -> Document:
    """Build a Document with sane defaults for tests."""
    return Document(
        id=uuid7(),
        text=text,
        source_path=Path("a.txt"),
        mime="text/plain",
        parser="plaintext",
        sha256=sha or ("a" * 64),
        char_count=len(text),
        extracted_at=datetime.now(timezone.utc),
    )


# ----------------------------- file_sha256 ---------------------------------


class TestFileSHA256:
    def test_deterministic(self, write_file):
        path = write_file("a.txt", "hello world")
        assert file_sha256(path) == file_sha256(path)

    def test_different_content_different_hash(self, write_file):
        a = write_file("a.txt", "hello")
        b = write_file("b.txt", "hello!")
        assert file_sha256(a) != file_sha256(b)

    def test_streaming_handles_large_files(self, tmp_path):
        # 5 MB file — bigger than the 64 KiB chunk to exercise the loop.
        path = tmp_path / "big.bin"
        path.write_bytes(b"x" * (5 * 1024 * 1024))
        digest = file_sha256(path)
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)


# ----------------------------- dedup_files ---------------------------------


class TestDedupFiles:
    def test_drops_identical_content(self, write_file):
        a = write_file("a.txt", "same content")
        b = write_file("b.txt", "same content")  # different name, same bytes
        c = write_file("c.txt", "different content")
        kept, dropped = dedup_files([a, b, c])
        assert kept == [a, c]
        assert dropped == [b]

    def test_preserves_first_occurrence(self, write_file):
        a = write_file("first.txt", "x")
        b = write_file("second.txt", "x")
        kept, _ = dedup_files([a, b])
        assert kept == [a]

    def test_empty_input(self):
        kept, dropped = dedup_files([])
        assert kept == []
        assert dropped == []

    def test_all_unique(self, write_file):
        files = [write_file(f"u{i}.txt", str(i)) for i in range(5)]
        kept, dropped = dedup_files(files)
        assert kept == files
        assert dropped == []


# ----------------------------- MinHash signature ---------------------------


class TestMakeMinhash:
    def test_identical_texts_match(self):
        a = make_minhash("the quick brown fox jumps over the lazy dog")
        b = make_minhash("the quick brown fox jumps over the lazy dog")
        assert a.jaccard(b) > 0.99

    def test_different_texts_low_jaccard(self):
        a = make_minhash("the quick brown fox jumps over the lazy dog")
        b = make_minhash("artificial intelligence transforms the future")
        assert a.jaccard(b) < 0.2

    def test_short_text_falls_back_to_whole(self):
        # Shorter than ngram_size still produces a valid signature.
        m = make_minhash("hi there", ngram_size=5)
        assert m.count() >= 0  # no crash; minhash exists

    def test_empty_text(self):
        # Empty text should not crash; produces an empty signature.
        m = make_minhash("", ngram_size=5)
        assert m is not None


# ----------------------------- dedup_documents -----------------------------


_LONG_TEXT_A = (
    "Large language models trained on web-scale corpora exhibit emergent "
    "behaviors when scaled past a certain parameter count. Researchers at "
    "leading labs have demonstrated that few-shot reasoning, code synthesis, "
    "and multi-step planning all improve smoothly with scale until they "
    "abruptly cross usability thresholds."
)

_LONG_TEXT_B_NEAR_DUPLICATE = (
    "Large language models trained on web-scale corpora exhibit emergent "
    "behaviors when scaled past a certain parameter count. Researchers at "
    "leading labs have demonstrated that few-shot reasoning, code synthesis, "
    "and multi-step planning all improve smoothly with scale until they "
    "suddenly cross usability thresholds."  # one word changed
)

_LONG_TEXT_C_UNRELATED = (
    "Brazilian cuisine reflects a deep blend of indigenous, African, and "
    "European influences, with regional dishes ranging from feijoada in the "
    "southeast to tacaca and acai bowls in the Amazon basin. Each region "
    "uses a distinctive set of tubers, fish, and spices."
)


class TestDedupDocuments:
    def test_empty(self):
        kept, removed = dedup_documents([])
        assert kept == []
        assert removed == []

    def test_single_doc_kept(self):
        d = _doc(_LONG_TEXT_A)
        kept, removed = dedup_documents([d])
        assert kept == [d]
        assert removed == []

    def test_exact_duplicates_collapse(self):
        a = _doc(_LONG_TEXT_A)
        b = _doc(_LONG_TEXT_A)
        kept, removed = dedup_documents([a, b])
        assert kept == [a]
        assert removed == [b.id]

    def test_near_duplicate_collapse(self):
        a = _doc(_LONG_TEXT_A)
        b = _doc(_LONG_TEXT_B_NEAR_DUPLICATE)
        kept, removed = dedup_documents([a, b], threshold=0.8)
        assert kept == [a]
        assert removed == [b.id]

    def test_unrelated_docs_kept(self):
        a = _doc(_LONG_TEXT_A)
        c = _doc(_LONG_TEXT_C_UNRELATED)
        kept, removed = dedup_documents([a, c])
        assert {d.id for d in kept} == {a.id, c.id}
        assert removed == []

    def test_higher_threshold_keeps_near_duplicates(self):
        # threshold=0.95 should NOT collapse the one-word-different pair.
        # (datasketch needs threshold <= ~0.95 with num_perm=128 to keep banding sane)
        a = _doc(_LONG_TEXT_A)
        b = _doc(_LONG_TEXT_B_NEAR_DUPLICATE)
        kept, removed = dedup_documents([a, b], threshold=0.95)
        assert len(kept) == 2
        assert removed == []

    def test_first_occurrence_kept(self):
        # When 3 near-identical docs come in, the first wins.
        a = _doc(_LONG_TEXT_A)
        b = _doc(_LONG_TEXT_A)
        c = _doc(_LONG_TEXT_A)
        kept, removed = dedup_documents([a, b, c])
        assert kept == [a]
        assert set(removed) == {b.id, c.id}
