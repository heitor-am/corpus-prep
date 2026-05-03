# corpus-prep

Open-source pipeline for preparing PT-BR LLM training corpora.

Ingests heterogeneous files (PDF, DOCX, PPTX, HTML, images, plain text) and produces Parquet shards ready for tokenization. Local OCR, encoding repair, language filtering, and deduplication — no paid APIs, no third-party services, runs on CPU.

## Status

End-to-end pipeline + CLI shipped (v0.1.0).

## Stack

| Layer | Tool |
|---|---|
| MIME detection | Magika |
| PDF (native text) | PyMuPDF4LLM |
| PDF (scanned) / DOCX / PPTX / images | Docling |
| HTML | Trafilatura |
| Encoding repair | ftfy |
| Language ID | GlotLID v3 (FastText backend) |
| Deduplication | SHA-256 (exact) + datasketch MinHash LSH (near) |
| Output | Apache Parquet (pyarrow, zstd) |
| Exploration | DuckDB |

All dependencies are open-source with permissive licenses. Runtime deps are listed in `pyproject.toml`.

## Quickstart

```bash
# 1. Setup
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# 2. Fetch the sample corpus (PT-BR municipal official journals) into data/raw
./scripts/fetch_sample_corpus.sh

# 3. (optional) download the GlotLID v3 model used by the language filter
./scripts/download_glotlid.sh

# 4. Run the pipeline
corpus-prep ingest data/raw -o data/corpus

# 5. Inspect
corpus-prep stats   data/corpus
corpus-prep explore data/corpus
```

The fetcher pulls from a public Google Drive folder via `gdown` — no OAuth as long as the folder is shared "Anyone with the link". Override the default source with `DRIVE_URL=...`. Drive rate-limits public-folder downloads, so the script retries with backoff and `gdown` skips files already on disk.

If you skip step 3, run `corpus-prep ingest --no-filter` so the pipeline doesn't try to load the GlotLID model.

## CLI overview

```bash
corpus-prep ingest <input-dir> -o <output-dir> [flags]
corpus-prep stats   <output-dir>
corpus-prep explore <output-dir>
```

Most useful `ingest` flags:

| Flag | Effect |
|---|---|
| `--no-filter` | Skip language ID and quality heuristics |
| `--no-pre-dedup` / `--no-post-dedup` | Skip the corresponding dedup stage |
| `--min-chars 200` | Length filter threshold |
| `--dedup-threshold 0.8` | Jaccard similarity threshold for MinHash LSH |
| `--max-docs-per-shard 10000` | Rotation point for the Parquet writer |
| `--glotlid models/glotlid.bin` | Path to the GlotLID model |

Run `corpus-prep ingest --help` for the full list.

## How it works

```
data/raw/  ─►  pre-dedup (SHA-256)  ─►  detect MIME (Magika)  ─►  parse  ─►
               normalize (ftfy + NFC + cleanup)  ─►  filter (length / lang / quality) ─►
               post-dedup (MinHash LSH)  ─►  Parquet shards + manifest.json
```

Each stage is a standalone module under `src/corpus_prep/` with its own tests. The pipeline orchestrator in `pipeline.py` runs them sequentially and collects a `RunReport` summarizing what happened.

## Concepts

### Trafilatura — main-content extraction

`trafilatura` is a Python library that extracts the **main content** of a web page. Given raw HTML, it removes boilerplate (navigation, ads, footers, comment threads, related-articles widgets) and returns only the paragraphs that carry the actual story.

Independent benchmarks (the Scrapinghub article-extraction benchmark, Trafilatura's own evaluation suite) place it at the top of the field with **F1 ≈ 0.945** — ahead of `readability-lxml`, `newspaper3k`, `goose3`, and `jusText`. It powers the **RefinedWeb** pipeline behind Falcon LLM and HuggingFace's `datatrove`.

In this repo it backs `parsers/html_parser.py`.

### Apache Parquet — columnar storage

Parquet is a columnar binary format optimized for analytical reads. Compared to JSONL or CSV it:

- Stores each column contiguously, so queries that touch a few columns skip the rest.
- Compresses each column with the codec best suited to its type — zstd for text, dictionary encoding for low-cardinality strings.
- Ships an embedded schema, so consumers don't need an external definition.
- Is the **default storage format** for HuggingFace Datasets and the most common shape for LLM training corpora.

`corpus-prep` writes shards with an explicit schema (defined in `src/corpus_prep/shard.py`), zstd-compressed at level 3, rotated by document count. See [`docs/refinedweb-summary.md`](./docs/refinedweb-summary.md) for the dataset that popularized this stack.

### Mojibake and ftfy

**Mojibake** (文字化け, "character transformation") is text that looks corrupted because it was decoded with the wrong encoding. The classic Brazilian-Portuguese case: UTF-8 text mis-decoded as Latin-1, producing sequences like `Ã©` instead of `é` or `nÃ£o` instead of `não`.

`ftfy` ("fixes text for you") is the de facto repair library. It detects the most common Latin-1 / Windows-1252 / UTF-8 confusions and reverses them. `corpus-prep` runs `ftfy.fix_text()` as the first step of `normalize.normalize()`, so every Document the pipeline emits is mojibake-free. See [`notebooks/ftfy_walkthrough.ipynb`](./notebooks/ftfy_walkthrough.ipynb) for a hands-on tour.

### Downstream applications

A *downstream application* is the final task you adapt a pre-trained model to. The pipeline-then-finetune pattern is the dominant LLM workflow:

1. **Pre-train** on a large corpus with self-supervised next-token prediction (the corpus this repo produces).
2. **Adapt** to a specific task with much smaller labeled data, via fine-tuning, instruction tuning, or in-context learning.

Common downstream tasks include:

| Category | Examples |
|---|---|
| Classification | sentiment analysis, toxicity detection, topic labeling |
| Information extraction | named entity recognition, relation extraction |
| Question answering | extractive QA, generative QA, multi-hop reasoning |
| Generation | summarization, translation, code synthesis, dialog |
| Retrieval-augmented | RAG, semantic search, recommendation explanations |

For Brazilian official-journal corpora specifically, plausible downstream use cases include automatic indexing of legal acts, summarization of municipal contracts, classification of administrative procedures, and entity extraction of public officials and supplier names.

## Notebooks

| Notebook | What it covers |
|---|---|
| [`ftfy_walkthrough.ipynb`](./notebooks/ftfy_walkthrough.ipynb) | Mojibake gallery and the normalization pipeline |
| [`dedup_walkthrough.ipynb`](./notebooks/dedup_walkthrough.ipynb) | Pre- and post-dedup with concrete examples |
| [`format_coverage.ipynb`](./notebooks/format_coverage.ipynb) | Multi-format pipeline run on a synthetic mini-corpus |
| [`duckdb_exploration.ipynb`](./notebooks/duckdb_exploration.ipynb) | SQL recipes over the Parquet output |

## Project layout

```
corpus-prep/
├── README.md                       <- you are here
├── pyproject.toml
├── docs/
│   └── refinedweb-summary.md
├── notebooks/
│   ├── ftfy_walkthrough.ipynb
│   ├── dedup_walkthrough.ipynb
│   ├── format_coverage.ipynb
│   └── duckdb_exploration.ipynb
├── scripts/
│   ├── download_glotlid.sh
│   └── fetch_sample_corpus.sh
├── src/corpus_prep/
│   ├── cli.py                      <- typer commands
│   ├── pipeline.py                 <- orchestrator
│   ├── shard.py                    <- Parquet writer
│   ├── parsers/                    <- 9 formats via Registry pattern
│   ├── detect.py                   <- Magika MIME
│   ├── normalize.py                <- ftfy + Unicode + cleanup
│   ├── filter.py                   <- length / language / repetition / char-ratio
│   ├── dedup.py                    <- SHA-256 + MinHash LSH
│   ├── schemas.py                  <- ParseResult / Document
│   └── utils/
└── tests/
```

## Development

```bash
# Run the test suite (excludes Docling-heavy slow tests)
PYTHONPATH=src pytest -m "not slow"

# Lint and type-check
ruff check src tests
mypy src
```

## References

- [The RefinedWeb Dataset for Falcon LLM — Penedo et al., 2023](https://arxiv.org/abs/2306.01116)
- [Trafilatura](https://github.com/adbar/trafilatura)
- [Docling](https://github.com/docling-project/docling)
- [datatrove (HuggingFace)](https://github.com/huggingface/datatrove)

## License

[MIT](./LICENSE).
