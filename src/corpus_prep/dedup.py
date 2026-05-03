"""Deduplication: exact (SHA-256 streaming) and MinHash LSH near-dedup.

Pre-dedup
    Removes byte-identical files before parsing. Useful when an inbox contains
    multiple copies of the same PDF under different names.

Post-dedup
    Removes near-duplicate Documents based on word n-gram Jaccard similarity.
    Catches paraphrased text, OCR variants of the same source, etc. Uses
    datasketch MinHash + LSH for O(N) approximate matching instead of O(N^2)
    pairwise Jaccard.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path
from uuid import UUID

from datasketch import MinHash, MinHashLSH

from corpus_prep.schemas import Document

# 64 KiB chunk for streaming hash — fits L2 cache, far below typical file sizes.
SHA256_CHUNK_SIZE = 64 * 1024


def file_sha256(path: Path) -> str:
    """Compute SHA-256 of the file content, streaming in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(SHA256_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def dedup_files(paths: Iterable[Path]) -> tuple[list[Path], list[Path]]:
    """Drop files with the same SHA-256.

    Returns:
        ``(kept, dropped)`` — the first occurrence of each unique hash is kept,
        subsequent occurrences land in ``dropped``. Order is preserved.
    """
    seen: dict[str, Path] = {}
    kept: list[Path] = []
    dropped: list[Path] = []
    for path in paths:
        digest = file_sha256(path)
        if digest in seen:
            dropped.append(path)
        else:
            seen[digest] = path
            kept.append(path)
    return kept, dropped


# ----------------------------- MinHash LSH ---------------------------------


def _ngrams(text: str, n: int) -> list[str]:
    """Word n-grams as space-joined tokens.

    For texts shorter than ``n`` words, the whole text becomes a single token —
    keeps short documents addressable in the LSH index.
    """
    words = text.split()
    if len(words) < n:
        return [" ".join(words)] if words else []
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]


def make_minhash(text: str, *, num_perm: int = 128, ngram_size: int = 5) -> MinHash:
    """Build a MinHash signature for ``text``.

    Public so notebooks and tests can inspect signatures directly.
    """
    m = MinHash(num_perm=num_perm)
    for ng in _ngrams(text, ngram_size):
        m.update(ng.encode("utf-8"))
    return m


def dedup_documents(
    docs: Iterable[Document],
    *,
    threshold: float = 0.8,
    num_perm: int = 128,
    ngram_size: int = 5,
) -> tuple[list[Document], list[UUID]]:
    """Drop near-duplicates using MinHash LSH.

    Args:
        docs: Documents to deduplicate (any iterable, consumed once).
        threshold: Jaccard similarity above which two documents are considered
            duplicates. Default 0.8 follows the FineWeb / datatrove convention.
        num_perm: Number of permutations for MinHash. 128 keeps memory low and
            still gives good accuracy at threshold=0.8.
        ngram_size: Word n-gram size. 5 is the de facto choice for medium-length
            documents — smaller n catches more, larger n is stricter.

    Returns:
        ``(kept_docs, removed_ids)`` — the first document of each cluster is
        kept; subsequent near-duplicates have their IDs returned in
        ``removed_ids``. Order of ``kept_docs`` follows insertion order.
    """
    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    kept: list[Document] = []
    removed_ids: list[UUID] = []

    for doc in docs:
        signature = make_minhash(doc.text, num_perm=num_perm, ngram_size=ngram_size)
        candidates = lsh.query(signature)
        if candidates:
            removed_ids.append(doc.id)
            continue
        # LSH keys must be strings — UUID hex preserves uniqueness.
        lsh.insert(str(doc.id), signature)
        kept.append(doc)

    return kept, removed_ids
