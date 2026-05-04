"""Quality audit for a corpus-prep Parquet output.

Reads ``<output_dir>/shard-*.parquet`` via DuckDB and prints a dashboard of
quality signals: size distribution, parser mix, suspicious documents, top
repeated n-grams (boilerplate detection), and a few random samples.

Usage:
    python scripts/audit_corpus.py data/corpus
    python scripts/audit_corpus.py data/corpus --samples 5
    python scripts/audit_corpus.py data/corpus --suspicious-threshold 500
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


# ----------------------------- helpers -------------------------------------


def _bucket_label(c: int) -> str:
    if c < 200:
        return "<200 (likely bad)"
    if c < 1_000:
        return "200-1k"
    if c < 5_000:
        return "1k-5k"
    if c < 20_000:
        return "5k-20k"
    if c < 100_000:
        return "20k-100k"
    return ">100k"


_BUCKET_ORDER = ["<200 (likely bad)", "200-1k", "1k-5k", "5k-20k", "20k-100k", ">100k"]


def _word_ratio(text: str) -> tuple[float, float]:
    """Return (avg_word_len, alpha_ratio)."""
    words = text.split()
    avg = sum(len(w) for w in words) / max(len(words), 1)
    alpha = sum(c.isalpha() for c in text) / max(len(text), 1)
    return avg, alpha


def _section(title: str) -> None:
    console.print()
    console.print(Panel.fit(title, style="bold cyan"))


# ----------------------------- main ---------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus_dir", type=Path, help="Directory with shard-*.parquet")
    parser.add_argument("--samples", type=int, default=3, help="Number of random sample docs to show.")
    parser.add_argument(
        "--suspicious-threshold",
        type=int,
        default=200,
        help="Char-count below which a document is flagged suspicious.",
    )
    parser.add_argument(
        "--top-ngrams",
        type=int,
        default=10,
        help="How many top repeated 5-grams to display.",
    )
    args = parser.parse_args()

    corpus_dir: Path = args.corpus_dir
    glob = str(corpus_dir / "shard-*.parquet")
    if not list(corpus_dir.glob("shard-*.parquet")):
        console.print(f"[red]No parquet shards under {corpus_dir}[/red]")
        raise SystemExit(1)

    con = duckdb.connect()
    con.execute(f"CREATE VIEW corpus AS SELECT * FROM '{glob}'")

    # ---- Summary ----
    _section("Corpus summary")
    summary: dict[str, Any] = con.execute(
        "SELECT COUNT(*) AS docs, "
        "SUM(char_count) AS total_chars, "
        "ROUND(AVG(char_count)) AS avg, "
        "MIN(char_count) AS min_, MAX(char_count) AS max_ "
        "FROM corpus"
    ).fetchone()
    docs, total_chars, avg, mn, mx = summary
    table = Table(show_header=False, box=None)
    table.add_column(style="cyan")
    table.add_column(justify="right")
    table.add_row("documents", f"{docs:,}")
    table.add_row("total chars", f"{total_chars:,}")
    table.add_row("avg chars/doc", f"{avg:,.0f}")
    table.add_row("min chars", f"{mn:,}")
    table.add_row("max chars", f"{mx:,}")
    console.print(table)

    # ---- Parser breakdown ----
    _section("Parser breakdown")
    rows = con.execute(
        "SELECT parser, COUNT(*) AS docs, ROUND(AVG(char_count)) AS avg_chars, "
        "SUM(char_count) AS total_chars "
        "FROM corpus GROUP BY parser ORDER BY docs DESC"
    ).fetchall()
    t = Table()
    t.add_column("Parser", style="cyan")
    t.add_column("Docs", justify="right")
    t.add_column("Avg chars", justify="right")
    t.add_column("Total chars", justify="right")
    for parser, n, avg_c, total in rows:
        t.add_row(parser, f"{n:,}", f"{int(avg_c or 0):,}", f"{int(total or 0):,}")
    console.print(t)

    # ---- Char count distribution ----
    _section("Char-count distribution")
    rows = con.execute(
        "SELECT char_count, source_path FROM corpus"
    ).fetchall()
    buckets: Counter[str] = Counter(_bucket_label(r[0]) for r in rows)
    t = Table()
    t.add_column("Bucket", style="cyan")
    t.add_column("Docs", justify="right")
    t.add_column("Bar", style="green")
    max_count = max(buckets.values()) if buckets else 1
    for label in _BUCKET_ORDER:
        n = buckets.get(label, 0)
        bar = "█" * int(40 * n / max_count) if max_count else ""
        t.add_row(label, f"{n:,}", bar)
    console.print(t)

    # ---- Suspicious docs ----
    _section(f"Suspicious documents (< {args.suspicious_threshold} chars)")
    rows = con.execute(
        "SELECT source_path, char_count, parser FROM corpus "
        f"WHERE char_count < {args.suspicious_threshold} "
        "ORDER BY char_count ASC"
    ).fetchall()
    if not rows:
        console.print("[green]None — every document cleared the threshold.[/green]")
    else:
        t = Table()
        t.add_column("source_path", style="cyan", overflow="fold")
        t.add_column("chars", justify="right")
        t.add_column("parser")
        for sp, cc, p in rows[:30]:
            t.add_row(sp, str(cc), p)
        if len(rows) > 30:
            t.add_row("...", f"+{len(rows) - 30} more", "")
        console.print(t)

    # ---- Word health ----
    _section("Word-level health (sample of up to 200 docs)")
    docs_sample = con.execute(
        "SELECT text FROM corpus ORDER BY RANDOM() LIMIT 200"
    ).fetchall()
    avgs, alphas = [], []
    for (txt,) in docs_sample:
        a, b = _word_ratio(txt)
        avgs.append(a)
        alphas.append(b)
    if avgs:
        t = Table(show_header=False, box=None)
        t.add_column(style="cyan")
        t.add_column(justify="right")
        t.add_row("avg word length (median)", f"{sorted(avgs)[len(avgs) // 2]:.2f}")
        t.add_row("alpha char ratio (median)", f"{sorted(alphas)[len(alphas) // 2]:.2%}")
        console.print(t)
        console.print(
            "[dim]Healthy PT-BR text usually shows avg word length ~5 and alpha ratio > 0.7.[/dim]"
        )

    # ---- Top repeated n-grams (boilerplate detection) ----
    _section(f"Top {args.top_ngrams} repeated 5-word phrases (boilerplate signal)")
    docs_ng = con.execute("SELECT text FROM corpus").fetchall()
    ngrams: Counter[str] = Counter()
    for (txt,) in docs_ng:
        words = re.findall(r"\w+", txt.lower())
        for i in range(len(words) - 4):
            ngrams[" ".join(words[i : i + 5])] += 1
    top = ngrams.most_common(args.top_ngrams)
    t = Table()
    t.add_column("5-gram", style="cyan", overflow="fold")
    t.add_column("Count", justify="right")
    for ng, n in top:
        t.add_row(ng, f"{n:,}")
    console.print(t)

    # ---- Random samples ----
    _section(f"{args.samples} random samples")
    samples = con.execute(
        f"SELECT source_path, parser, char_count, text FROM corpus "
        f"ORDER BY RANDOM() LIMIT {args.samples}"
    ).fetchall()
    for sp, parser, cc, txt in samples:
        preview = txt[:300] + ("..." if len(txt) > 300 else "")
        console.print(
            Panel(
                preview,
                title=f"{sp}  •  {parser}  •  {cc:,} chars",
                style="dim",
                title_align="left",
            )
        )


if __name__ == "__main__":
    main()
