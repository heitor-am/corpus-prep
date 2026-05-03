# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-05-03

First public release. End-to-end pipeline for preparing PT-BR LLM training
corpora with no paid APIs or third-party services.

### Added

- **CLI** — `corpus-prep ingest`, `corpus-prep stats`, `corpus-prep explore`
  with rich terminal output (Typer + Rich).
- **Parsers** for nine formats via a Registry pattern: TXT, MD, CSV, JSON,
  HTML (Trafilatura), PDF native (PyMuPDF4LLM), DOCX / PPTX / images
  (Docling).
- **Magika-based MIME detection** with confidence threshold and
  `application/octet-stream` fallback.
- **Normalization** — `ftfy.fix_text` + Unicode NFC + control-char strip +
  whitespace collapse.
- **Quality filtering** — length, language (GlotLID v3 via FastText),
  repetition, and char-ratio heuristics. Aggregates rejection counts in the
  `RunReport`.
- **Deduplication** — exact (SHA-256 streaming) and near (datasketch
  MinHash LSH at Jaccard 0.8 by default).
- **Parquet sharding** — explicit schema with eleven fields including a
  `metadata: map<string, string>` column. zstd-3 compression. Sidecar
  `manifest.json` per output directory.
- **DuckDB integration** — canned SQL queries powering the `explore`
  subcommand and the `duckdb_exploration.ipynb` notebook.
- **Notebooks** — `ftfy_walkthrough`, `dedup_walkthrough`,
  `format_coverage`, `duckdb_exploration`.
- **Scripts** — `fetch_sample_corpus.sh` (Drive via gdown, retry on rate
  limit), `download_glotlid.sh`, `benchmark.py` (synthetic-corpus
  performance run).
- **Tooling** — `ruff`, `mypy --strict`, pre-commit hooks, project-level
  `.claude/hooks/git-guard.sh` enforcing Conventional Commits.
- **Documentation** — `PRD.md` (full architectural spec) and
  `docs/refinedweb-summary.md`.

### Quality bar

- 118 unit + integration tests, 91% line coverage.
- `mypy --strict` clean across `src/`.
- `ruff check` clean across `src/` and `tests/`.

### Known limitations

- Audio and video formats are out of scope for this release.
- Pipeline runs single-process; concurrency is on the roadmap behind a
  flag.
- Docling's first-use download of layout / OCR models can take several
  minutes; non-Docling formats run instantly.

[Unreleased]: https://github.com/heitor-am/corpus-prep/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/heitor-am/corpus-prep/releases/tag/v0.1.0
