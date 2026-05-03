"""Synthetic-corpus benchmark for the full corpus-prep pipeline.

Generates a configurable mix of PDF / TXT / JSON / HTML files, runs the
pipeline, and prints throughput numbers. Used to gauge performance on a
controlled workload before pointing the pipeline at a real corpus.

Usage::

    python scripts/benchmark.py --pdfs 50 --texts 100 --filter

Requires the ``[dev]`` extras (reportlab + the pipeline runtime stack).
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from corpus_prep.filter import FilterConfig
from corpus_prep.pipeline import Pipeline, PipelineConfig

PARAGRAPH = (
    "Modelos de linguagem treinados em corpora de larga escala demonstram "
    "comportamentos emergentes a partir de certo numero de parametros. "
    "Pesquisadores em laboratorios de ponta tem demonstrado que a capacidade "
    "de raciocinio em poucos exemplos melhora suavemente com a escala. "
)


@dataclass
class _MockLang:
    label: str = "por_Latn"
    confidence: float = 0.97

    def predict(self, text: str) -> tuple[str, float]:  # noqa: ARG002
        return self.label, self.confidence


def _make_pdf(path: Path, paragraphs: int = 5) -> None:
    """Generate a multi-page PDF with native text via ReportLab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont("Helvetica", 10)
    for _ in range(paragraphs):
        y = 800
        for line in (PARAGRAPH * 3).split(". "):
            c.drawString(50, y, (line + ".").strip())
            y -= 14
            if y < 60:
                c.showPage()
                c.setFont("Helvetica", 10)
                y = 800
        c.showPage()
        c.setFont("Helvetica", 10)
    c.save()


def _make_corpus(input_dir: Path, n_pdfs: int, n_texts: int) -> int:
    """Populate ``input_dir`` and return the total file count."""
    input_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n_pdfs):
        _make_pdf(input_dir / f"pdf_{i:04d}.pdf")
    for i in range(n_texts):
        # Vary the text so post-dedup keeps everything.
        suffix = f" Variant {i} adds local color and unique tokens to the text."
        (input_dir / f"text_{i:04d}.txt").write_text(PARAGRAPH * 5 + suffix)
        if i % 4 == 0:
            (input_dir / f"meta_{i:04d}.json").write_text(
                json.dumps({"id": i, "summary": PARAGRAPH * 2 + suffix})
            )
        if i % 5 == 0:
            (input_dir / f"page_{i:04d}.html").write_text(
                f"<html><body><article><p>{PARAGRAPH * 3}{suffix}</p>"
                f"</article></body></html>"
            )
    return sum(1 for _ in input_dir.iterdir())


def _print_block(title: str, rows: dict[str, str]) -> None:
    print(f"\n{title}")
    width = max(len(k) for k in rows) + 2
    for k, v in rows.items():
        print(f"  {k.ljust(width)} {v}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdfs", type=int, default=20, help="Number of PDFs to generate.")
    parser.add_argument("--texts", type=int, default=50, help="Number of text files to generate.")
    parser.add_argument(
        "--filter", action="store_true", help="Enable the language/quality filter."
    )
    parser.add_argument(
        "--keep", action="store_true", help="Keep the temp directory for inspection."
    )
    args = parser.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="corpus-prep-bench-"))
    in_dir = tmp / "in"
    out_dir = tmp / "out"

    print(f"Building synthetic corpus under {in_dir}...")
    t0 = time.perf_counter()
    file_count = _make_corpus(in_dir, args.pdfs, args.texts)
    t_corpus = time.perf_counter() - t0

    total_input_bytes = sum(p.stat().st_size for p in in_dir.iterdir() if p.is_file())
    _print_block(
        "Corpus generation",
        {
            "files":      f"{file_count}",
            "size":       f"{total_input_bytes / (1024 * 1024):.2f} MiB",
            "elapsed":    f"{t_corpus:.2f}s",
            "throughput": f"{file_count / max(t_corpus, 0.001):.1f} files/s",
        },
    )

    config = PipelineConfig(
        input_dir=in_dir,
        output_dir=out_dir,
        filter_config=FilterConfig(min_chars=200),
        enable_filter=args.filter,
    )
    predictor = _MockLang() if args.filter else None

    print("\nRunning pipeline...")
    t0 = time.perf_counter()
    report = Pipeline(config, language_predictor=predictor).run()
    t_pipeline = time.perf_counter() - t0

    output_bytes = sum(
        p.stat().st_size for p in out_dir.iterdir() if p.is_file()
    )

    _print_block(
        "Pipeline run",
        {
            "input files":          f"{report.input_files}",
            "after pre-dedup":      f"{report.pre_dedup_kept}",
            "parsed":               f"{report.parsed}",
            "parse failures":       f"{report.parse_failure_count}",
            "filter passed":        f"{report.filter_passed}",
            "filter rejected":      f"{report.filter_rejected}",
            "after post-dedup":     f"{report.post_dedup_kept}",
            "post-dedup removed":   f"{report.post_dedup_removed}",
            "shards written":       f"{report.shards_written}",
            "total chars":          f"{report.total_chars_written:,}",
            "duration":             f"{report.duration_seconds:.2f}s",
        },
    )

    files_per_sec = report.input_files / max(t_pipeline, 0.001)
    mib_per_sec = total_input_bytes / (1024 * 1024) / max(t_pipeline, 0.001)
    _print_block(
        "Throughput",
        {
            "files/s":         f"{files_per_sec:.1f}",
            "MiB/s (input)":   f"{mib_per_sec:.2f}",
            "compression":     f"{output_bytes / max(total_input_bytes, 1):.2%}",
        },
    )

    if args.keep:
        print(f"\nLeft corpus and output in {tmp}")
    else:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
