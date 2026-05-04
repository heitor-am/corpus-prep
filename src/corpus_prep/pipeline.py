"""Linear pipeline orchestrator.

Stages (in order):

    1. discover      — walk input_dir, collect files
    2. pre-dedup     — drop byte-identical files (SHA-256)
    3. parse         — detect MIME, route to parser, build a ParseResult
    4. normalize     — ftfy + Unicode NFC + whitespace cleanup
    5. filter        — length, language (LID), repetition, char_ratio
    6. post-dedup    — MinHash LSH on normalized text
    7. shard         — write Parquet shards + manifest.json

Concurrency is intentionally not used here: parser singletons (Magika, Docling)
re-init per process and Document pickling adds friction. At the typical corpus
scale this targets (hundreds of MB), single-process is fast enough. A future
ProcessPoolExecutor variant can sit behind a ``concurrent=True`` flag.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from datasketch import MinHashLSH
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from corpus_prep.dedup import dedup_files, file_sha256, make_minhash
from corpus_prep.detect import detect_mime
from corpus_prep.filter import (
    DEFAULT_GLOTLID_PATH,
    FilterConfig,
    LanguageIdentifier,
    LanguagePredictor,
    is_valid,
)
from corpus_prep.normalize import normalize
from corpus_prep.parsers import (
    ParserError,
    UnsupportedFormatError,
    get_parser,
)
from corpus_prep.schemas import Document, ParseResult
from corpus_prep.shard import ShardWriter
from corpus_prep.utils.ids import uuid7


@dataclass
class PipelineConfig:
    """End-to-end pipeline configuration."""

    input_dir: Path
    output_dir: Path
    filter_config: FilterConfig = field(default_factory=FilterConfig)
    enable_filter: bool = True
    enable_pre_dedup: bool = True
    enable_post_dedup: bool = True
    dedup_threshold: float = 0.8
    dedup_num_perm: int = 128
    dedup_ngram_size: int = 5
    max_docs_per_shard: int = 10_000
    glotlid_path: Path = DEFAULT_GLOTLID_PATH
    show_progress: bool = True
    enable_ocr_fallback: bool = True

    def to_serializable(self) -> dict[str, Any]:
        """Snapshot used inside the manifest's ``config`` field."""
        return {
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "enable_filter": self.enable_filter,
            "enable_pre_dedup": self.enable_pre_dedup,
            "enable_post_dedup": self.enable_post_dedup,
            "dedup_threshold": self.dedup_threshold,
            "dedup_num_perm": self.dedup_num_perm,
            "dedup_ngram_size": self.dedup_ngram_size,
            "max_docs_per_shard": self.max_docs_per_shard,
            "enable_ocr_fallback": self.enable_ocr_fallback,
            "filter": {
                "min_chars": self.filter_config.min_chars,
                "expected_language": self.filter_config.expected_language,
                "min_lang_confidence": self.filter_config.min_lang_confidence,
                "max_non_alpha_ratio": self.filter_config.max_non_alpha_ratio,
                "min_unique_word_ratio": self.filter_config.min_unique_word_ratio,
            },
        }


@dataclass
class ParseFailure:
    """Captured for the report when a single file fails."""

    path: Path
    stage: str  # 'detect' | 'registry' | 'parse'
    error_type: str
    error_message: str


@dataclass
class RunReport:
    """Per-run summary returned by ``Pipeline.run()``."""

    input_files: int = 0
    pre_dedup_kept: int = 0
    parsed: int = 0
    parse_failures: list[ParseFailure] = field(default_factory=list)
    filter_passed: int = 0
    filter_rejected: dict[str, int] = field(default_factory=dict)
    post_dedup_kept: int = 0
    post_dedup_removed: int = 0
    ocr_fallback_count: int = 0
    shards_written: int = 0
    total_chars_written: int = 0
    duration_seconds: float = 0.0

    @property
    def parse_failure_count(self) -> int:
        return len(self.parse_failures)


class Pipeline:
    """Sequential orchestrator. Inject a ``language_predictor`` for tests."""

    def __init__(
        self,
        config: PipelineConfig,
        *,
        language_predictor: LanguagePredictor | None = None,
    ) -> None:
        self.config = config
        if config.enable_filter:
            self.language_predictor: LanguagePredictor | None = (
                language_predictor or LanguageIdentifier(config.glotlid_path)
            )
        else:
            self.language_predictor = None

    def run(self) -> RunReport:
        """Execute the full pipeline and return a RunReport.

        The pipeline streams: each parsed Document goes straight through
        normalize -> filter -> online MinHash LSH -> ShardWriter. Shard files
        rotate to disk as soon as ``max_docs_per_shard`` is reached, so the
        output directory grows incrementally and a Rich progress bar updates
        per input file. No in-memory backlog of all Documents.
        """
        start = time.perf_counter()
        report = RunReport()

        # 1. Discover.
        files = sorted(self._discover())
        report.input_files = len(files)

        # 2. Pre-dedup.
        if self.config.enable_pre_dedup and files:
            files, _dropped = dedup_files(files)
        report.pre_dedup_kept = len(files)

        # Online MinHash index for streaming post-dedup.
        lsh: MinHashLSH | None = None
        if self.config.enable_post_dedup:
            lsh = MinHashLSH(
                threshold=self.config.dedup_threshold,
                num_perm=self.config.dedup_num_perm,
            )

        progress_columns = (
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        )

        with ShardWriter(
            self.config.output_dir,
            max_docs_per_shard=self.config.max_docs_per_shard,
            config=self.config.to_serializable(),
        ) as writer, Progress(
            *progress_columns,
            disable=not self.config.show_progress,
            transient=False,
        ) as progress:
            task = progress.add_task(
                f"Ingesting {self.config.input_dir.name}", total=len(files)
            )
            for path in files:
                progress.update(task, description=f"Parsing {path.name}"[:80])
                doc = self._process_one(path, report)
                if doc is None:
                    progress.advance(task)
                    continue

                # Online near-dedup.
                if lsh is not None:
                    signature = make_minhash(
                        doc.text,
                        num_perm=self.config.dedup_num_perm,
                        ngram_size=self.config.dedup_ngram_size,
                    )
                    if lsh.query(signature):
                        report.post_dedup_removed += 1
                        progress.advance(task)
                        continue
                    lsh.insert(str(doc.id), signature)

                writer.write(doc)
                report.post_dedup_kept += 1
                progress.advance(task)

            progress.update(task, description="Finalizing shards")

        manifest = writer.manifest
        assert manifest is not None
        report.shards_written = len(manifest.shards)
        report.total_chars_written = manifest.total_chars

        report.duration_seconds = time.perf_counter() - start
        return report

    # ------------------------------ internals ------------------------------

    def _discover(self) -> Iterable[Path]:
        """Recursively yield files under ``input_dir``, skipping the output dir.

        When ``output_dir`` lives inside ``input_dir`` (e.g.
        ``corpus-prep ingest data -o data/corpus``), naive rglob would feed
        previously written shards back into the next run. We resolve both paths
        and exclude any candidate inside the output tree.
        """
        output_resolved = self.config.output_dir.resolve()
        for path in self.config.input_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.resolve().is_relative_to(output_resolved):
                continue
            yield path

    def _apply_ocr_fallback(self, path: Path, sparse: ParseResult) -> ParseResult | None:
        """Re-parse ``path`` through DoclingParser to recover OCR-required content.

        Returns ``None`` when Docling is unavailable or the OCR run itself fails;
        the caller keeps the sparse native result in that case.
        """
        try:
            from corpus_prep.parsers.docling_parser import DoclingParser
        except ImportError:
            return None

        try:
            ocr = DoclingParser().parse(path)
        except (ImportError, ParserError):
            return None
        except Exception:
            return None

        return ParseResult(
            text=ocr.text,
            parser_name="pdf-ocr-fallback",
            char_count=ocr.char_count,
            page_count=sparse.page_count,
            metadata={
                **ocr.metadata,
                "fallback_reason": "sparse_native_extraction",
                "native_chars_per_page": sparse.metadata.get("chars_per_page", "0"),
            },
        )

    def _process_one(self, path: Path, report: RunReport) -> Document | None:
        """Run detect -> parse -> normalize -> filter for a single file."""
        try:
            mime = detect_mime(path)
        except Exception as exc:
            report.parse_failures.append(
                ParseFailure(path, "detect", type(exc).__name__, str(exc))
            )
            return None

        try:
            parser = get_parser(mime, source=path)
        except UnsupportedFormatError as exc:
            report.parse_failures.append(
                ParseFailure(path, "registry", "UnsupportedFormatError", str(exc))
            )
            return None

        try:
            result = parser.parse(path)
        except ParserError as exc:
            report.parse_failures.append(
                ParseFailure(path, parser.name, "ParserError", str(exc))
            )
            return None
        except Exception as exc:
            report.parse_failures.append(
                ParseFailure(path, parser.name, type(exc).__name__, str(exc))
            )
            return None

        # OCR fallback: when the native PDF parser flags needs_ocr, replay through
        # Docling. Skipped silently when Docling is not installed or the OCR run
        # itself errors out — the sparse native result is still emitted in that case.
        if (
            self.config.enable_ocr_fallback
            and mime == "application/pdf"
            and result.metadata.get("needs_ocr") == "true"
        ):
            ocr_result = self._apply_ocr_fallback(path, result)
            if ocr_result is not None:
                result = ocr_result
                report.ocr_fallback_count += 1

        report.parsed += 1

        normalized_text = normalize(result.text)

        language: str | None = None
        confidence: float | None = None
        if self.config.enable_filter and self.language_predictor is not None:
            verdict = is_valid(
                normalized_text, self.config.filter_config, self.language_predictor
            )
            if not verdict.passed:
                reason = verdict.rejected_by or "unknown"
                report.filter_rejected[reason] = (
                    report.filter_rejected.get(reason, 0) + 1
                )
                return None
            report.filter_passed += 1
            language = verdict.detected_language
            confidence = verdict.language_confidence

        return Document(
            id=uuid7(),
            text=normalized_text,
            source_path=path.relative_to(self.config.input_dir),
            mime=mime,
            parser=result.parser_name,
            sha256=file_sha256(path),
            char_count=len(normalized_text),
            extracted_at=datetime.now(UTC),
            language=language,
            language_confidence=confidence,
            metadata=result.metadata,
        )

def run_pipeline(
    config: PipelineConfig,
    *,
    language_predictor: LanguagePredictor | None = None,
) -> RunReport:
    """Module-level convenience wrapper around :class:`Pipeline`."""
    return Pipeline(config, language_predictor=language_predictor).run()
