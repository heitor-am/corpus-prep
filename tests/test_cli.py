"""CLI smoke tests via Typer's CliRunner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from corpus_prep.cli import app

runner = CliRunner()


@pytest.fixture
def mini_corpus(tmp_path: Path) -> Path:
    """Create a tiny input directory with two distinct text files."""
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "a.txt").write_text(
        "Modelos de linguagem treinados em corpora de larga escala "
        "demonstram comportamentos emergentes a partir de certo numero "
        "de parametros. Pesquisadores em laboratorios de ponta tem "
        "demonstrado que a capacidade de raciocinio em poucos exemplos "
        "melhora suavemente com a escala."
    )
    (in_dir / "b.json").write_text(
        json.dumps(
            {
                "text": "A culinaria nordestina combina mandioca, peixes do "
                "litoral e temperos tradicionais como coentro, urucum e "
                "pimenta de cheiro. Pratos como o baiao de dois mostram a "
                "influencia dos fluxos migratorios entre o sertao e a costa."
            }
        )
    )
    return in_dir


def _run_ingest_no_filter(in_dir: Path, out_dir: Path):
    return runner.invoke(
        app,
        [
            "ingest",
            str(in_dir),
            "-o",
            str(out_dir),
            "--no-filter",
        ],
    )


# ----------------------------- ingest --------------------------------------


class TestIngest:
    def test_runs_end_to_end(self, mini_corpus: Path, tmp_path: Path):
        out_dir = tmp_path / "out"
        result = _run_ingest_no_filter(mini_corpus, out_dir)

        assert result.exit_code == 0, result.stdout
        assert (out_dir / "manifest.json").exists()
        assert any(out_dir.glob("shard-*.parquet"))
        assert "Run Report" in result.stdout

    def test_missing_input_dir_errors(self, tmp_path: Path):
        result = runner.invoke(
            app,
            [
                "ingest",
                str(tmp_path / "does-not-exist"),
                "-o",
                str(tmp_path / "out"),
                "--no-filter",
            ],
        )
        assert result.exit_code != 0

    def test_dedup_threshold_validated(self, mini_corpus: Path, tmp_path: Path):
        result = runner.invoke(
            app,
            [
                "ingest",
                str(mini_corpus),
                "-o",
                str(tmp_path / "out"),
                "--no-filter",
                "--dedup-threshold",
                "1.5",  # out of [0, 1]
            ],
        )
        assert result.exit_code != 0


# ----------------------------- stats ---------------------------------------


class TestStats:
    def test_pretty_prints_manifest(self, mini_corpus: Path, tmp_path: Path):
        out_dir = tmp_path / "out"
        _run_ingest_no_filter(mini_corpus, out_dir)

        result = runner.invoke(app, ["stats", str(out_dir)])
        assert result.exit_code == 0, result.stdout
        assert "Total documents" in result.stdout
        assert "Documents per parser" in result.stdout

    def test_missing_manifest_errors(self, tmp_path: Path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = runner.invoke(app, ["stats", str(empty_dir)])
        assert result.exit_code != 0


# ----------------------------- explore -------------------------------------


class TestExplore:
    def test_runs_canned_queries(self, mini_corpus: Path, tmp_path: Path):
        out_dir = tmp_path / "out"
        _run_ingest_no_filter(mini_corpus, out_dir)

        result = runner.invoke(app, ["explore", str(out_dir)])
        assert result.exit_code == 0, result.stdout
        assert "Total documents" in result.stdout
        assert "Top 5 parsers" in result.stdout
        assert "Language distribution" in result.stdout

    def test_no_shards_errors(self, tmp_path: Path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = runner.invoke(app, ["explore", str(empty_dir)])
        assert result.exit_code != 0
