"""Typer-based CLI: ingest, stats, explore."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from corpus_prep.filter import DEFAULT_GLOTLID_PATH, FilterConfig
from corpus_prep.pipeline import PipelineConfig, run_pipeline
from corpus_prep.shard import MANIFEST_FILENAME

app = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    help="Open-source pipeline for preparing PT-BR LLM training corpora.",
)
console = Console()


# ----------------------------- ingest --------------------------------------


@app.command()
def ingest(
    input_dir: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=False, dir_okay=True, resolve_path=True,
                        help="Directory walked recursively for source files."),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output", "-o", file_okay=False, dir_okay=True,
            help="Output directory for shard-*.parquet and manifest.json.",
        ),
    ],
    min_chars: Annotated[
        int, typer.Option("--min-chars", help="Drop documents shorter than this.")
    ] = 200,
    no_filter: Annotated[
        bool, typer.Option("--no-filter", help="Skip language and quality filters.")
    ] = False,
    no_pre_dedup: Annotated[
        bool, typer.Option("--no-pre-dedup", help="Skip byte-identical file dedup.")
    ] = False,
    no_post_dedup: Annotated[
        bool, typer.Option("--no-post-dedup", help="Skip MinHash near-duplicate dedup.")
    ] = False,
    dedup_threshold: Annotated[
        float, typer.Option("--dedup-threshold", min=0.0, max=1.0,
                              help="Jaccard threshold for MinHash LSH (0-1).")
    ] = 0.8,
    max_docs_per_shard: Annotated[
        int, typer.Option("--max-docs-per-shard", min=1)
    ] = 10_000,
    glotlid: Annotated[
        Path,
        typer.Option("--glotlid", help="Path to GlotLID v3 .bin (used by language filter)."),
    ] = DEFAULT_GLOTLID_PATH,
) -> None:
    """Run the full ingest pipeline on INPUT_DIR.

    Discovers files, deduplicates, parses, normalizes, filters by language and
    writes Parquet shards + manifest.json under -o/--output.
    """
    config = PipelineConfig(
        input_dir=input_dir,
        output_dir=output,
        filter_config=FilterConfig(min_chars=min_chars),
        enable_filter=not no_filter,
        enable_pre_dedup=not no_pre_dedup,
        enable_post_dedup=not no_post_dedup,
        dedup_threshold=dedup_threshold,
        max_docs_per_shard=max_docs_per_shard,
        glotlid_path=glotlid,
    )

    console.print(f"[bold]Input :[/bold] {config.input_dir}")
    console.print(f"[bold]Output:[/bold] {config.output_dir}")
    console.print()

    with console.status("[bold green]Running pipeline..."):
        report = run_pipeline(config)

    _print_run_report(report)


def _print_run_report(report) -> None:  # type: ignore[no-untyped-def]
    table = Table(title="Run Report", show_header=False, box=None, pad_edge=False)
    table.add_column(style="cyan")
    table.add_column(style="white", justify="right")

    table.add_row("input files", str(report.input_files))
    table.add_row("after pre-dedup", str(report.pre_dedup_kept))
    table.add_row("parsed", str(report.parsed))
    if report.parse_failures:
        table.add_row("parse failures", str(len(report.parse_failures)))
    if report.filter_passed or report.filter_rejected:
        table.add_row("filter passed", str(report.filter_passed))
        for reason, count in report.filter_rejected.items():
            table.add_row(f"  rejected ({reason})", str(count))
    table.add_row("after post-dedup", str(report.post_dedup_kept))
    if report.post_dedup_removed:
        table.add_row("post-dedup removed", str(report.post_dedup_removed))
    table.add_row("shards written", str(report.shards_written))
    table.add_row("total chars", f"{report.total_chars_written:,}")
    table.add_row("duration", f"{report.duration_seconds:.2f}s")

    console.print(table)


# ----------------------------- stats ---------------------------------------


@app.command()
def stats(
    corpus_dir: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=False, dir_okay=True, resolve_path=True,
                        help="Directory containing shard-*.parquet and manifest.json."),
    ],
) -> None:
    """Pretty-print manifest.json + per-parser/language counts via DuckDB."""
    manifest_path = corpus_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        console.print(f"[red]No manifest.json under {corpus_dir}[/red]")
        raise typer.Exit(code=1)

    manifest = json.loads(manifest_path.read_text())

    console.print(f"[bold]Corpus directory:[/bold] {corpus_dir}")
    console.print(f"Schema version : {manifest['schema_version']}")
    console.print(f"Created at     : {manifest['created_at']}")
    console.print(f"Total documents: {manifest['total_documents']:,}")
    console.print(f"Total chars    : {manifest['total_chars']:,}")
    console.print()

    # Shards table.
    shards_table = Table(title="Shards", show_lines=False)
    shards_table.add_column("Path", style="cyan")
    shards_table.add_column("Docs", justify="right")
    shards_table.add_column("Bytes", justify="right")
    shards_table.add_column("SHA256 (head)", style="dim")
    for shard in manifest["shards"]:
        shards_table.add_row(
            shard["path"],
            f"{shard['document_count']:,}",
            f"{shard['byte_size']:,}",
            shard["sha256"][:16],
        )
    console.print(shards_table)
    console.print()

    # DuckDB aggregates over the parquet files.
    if not list(corpus_dir.glob("shard-*.parquet")):
        console.print("[yellow]No parquet shards found; skipping DuckDB stats.[/yellow]")
        return

    import duckdb

    glob = str(corpus_dir / "shard-*.parquet")
    con = duckdb.connect()

    by_parser = con.execute(
        f"SELECT parser, COUNT(*) AS docs, SUM(char_count) AS chars "
        f"FROM '{glob}' GROUP BY parser ORDER BY docs DESC"
    ).fetchall()
    parser_table = Table(title="Documents per parser")
    parser_table.add_column("Parser", style="cyan")
    parser_table.add_column("Docs", justify="right")
    parser_table.add_column("Chars", justify="right")
    for parser, docs, chars in by_parser:
        parser_table.add_row(parser, f"{docs:,}", f"{int(chars or 0):,}")
    console.print(parser_table)
    console.print()

    by_language = con.execute(
        f"SELECT COALESCE(language, '<unknown>') AS lang, COUNT(*) AS docs "
        f"FROM '{glob}' GROUP BY lang ORDER BY docs DESC"
    ).fetchall()
    lang_table = Table(title="Documents per language")
    lang_table.add_column("Language", style="cyan")
    lang_table.add_column("Docs", justify="right")
    for lang, docs in by_language:
        lang_table.add_row(lang, f"{docs:,}")
    console.print(lang_table)


# ----------------------------- explore -------------------------------------


_EXPLORE_QUERIES: list[tuple[str, str]] = [
    (
        "Total documents",
        "SELECT COUNT(*) AS n FROM '{glob}'",
    ),
    (
        "Average char count",
        "SELECT ROUND(AVG(char_count), 1) AS avg_chars FROM '{glob}'",
    ),
    (
        "Top 5 parsers",
        "SELECT parser, COUNT(*) AS n FROM '{glob}' GROUP BY parser ORDER BY n DESC LIMIT 5",
    ),
    (
        "Top 5 source paths",
        "SELECT source_path, char_count FROM '{glob}' ORDER BY char_count DESC LIMIT 5",
    ),
    (
        "Language distribution",
        "SELECT COALESCE(language, '<unknown>') AS lang, COUNT(*) AS n "
        "FROM '{glob}' GROUP BY lang ORDER BY n DESC",
    ),
    (
        "Sample 3 docs (first 80 chars)",
        "SELECT source_path, SUBSTR(text, 1, 80) || '...' AS preview "
        "FROM '{glob}' LIMIT 3",
    ),
]


@app.command()
def explore(
    corpus_dir: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    ],
) -> None:
    """Run a fixed set of educational DuckDB queries over the corpus."""
    if not list(corpus_dir.glob("shard-*.parquet")):
        console.print(f"[red]No parquet shards under {corpus_dir}[/red]")
        raise typer.Exit(code=1)

    import duckdb

    glob = str(corpus_dir / "shard-*.parquet")
    con = duckdb.connect()

    console.print(f"[bold]Querying:[/bold] {glob}")
    console.print()

    for label, query_template in _EXPLORE_QUERIES:
        query = query_template.format(glob=glob)
        console.print(f"[bold cyan]>> {label}[/bold cyan]")
        console.print(f"[dim]{query}[/dim]")
        result = con.execute(query).fetchall()
        if not result:
            console.print("[yellow]<no rows>[/yellow]\n")
            continue
        # Use the column descriptions for the header.
        cols = [d[0] for d in con.description]
        table = Table(show_header=True, header_style="bold")
        for col in cols:
            table.add_column(col)
        for row in result:
            table.add_row(*[str(v) for v in row])
        console.print(table)
        console.print()


def main() -> None:
    """Module entry-point used by ``corpus-prep`` and ``python -m corpus_prep.cli``."""
    app()


if __name__ == "__main__":
    main()
