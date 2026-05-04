"""End-to-end pipeline tests against a synthetic corpus.

Uses a mock LanguagePredictor so tests don't depend on the GlotLID model file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pyarrow.parquet as pq

from corpus_prep.filter import DEFAULT_PT_LABEL, FilterConfig
from corpus_prep.pipeline import Pipeline, PipelineConfig
from corpus_prep.shard import MANIFEST_FILENAME


@dataclass
class MockLangPredictor:
    """Always returns ``por_Latn`` with high confidence."""

    label: str = DEFAULT_PT_LABEL
    confidence: float = 0.99

    def predict(self, text: str) -> tuple[str, float]:
        return self.label, self.confidence


def _mk_corpus(input_dir: Path) -> dict[str, Path]:
    """Create a small heterogeneous corpus with topic-distinct documents.

    Each format hosts a different topic so MinHash post-dedup leaves them
    intact. Includes a duplicate (``a.txt`` == ``a_dup.txt``) so the pre-dedup
    branch fires deterministically; ``short.txt`` is below the length filter.
    """
    input_dir.mkdir(parents=True, exist_ok=True)
    files = {}

    text_a_llms = (
        "Modelos de linguagem treinados em corpora de larga escala demonstram "
        "comportamentos emergentes a partir de certo numero de parametros. "
        "Pesquisadores em laboratorios de ponta tem demonstrado que a capacidade "
        "de raciocinio em poucos exemplos melhora suavemente com a escala. " * 2
    )
    text_b_cooking = (
        "A culinaria nordestina combina mandioca, peixes do litoral e temperos "
        "tradicionais como coentro, urucum e pimenta de cheiro. Pratos como o "
        "baiao de dois e a paçoca de carne de sol mostram a influencia dos "
        "fluxos migratorios entre o sertao e a costa. " * 2
    )
    text_c_geography = (
        "O bioma da caatinga ocupa parte significativa do interior nordestino "
        "e abriga especies adaptadas a longos periodos de estiagem. A vegetacao "
        "predominante inclui arvores de pequeno porte, cactos e plantas com "
        "mecanismos de armazenamento de agua bem desenvolvidos. " * 2
    )

    files["a.txt"] = input_dir / "a.txt"
    files["a.txt"].write_text(text_a_llms)

    files["a_dup.txt"] = input_dir / "a_dup.txt"
    files["a_dup.txt"].write_text(text_a_llms)  # byte-identical -> pre-dedup

    files["b.json"] = input_dir / "b.json"
    files["b.json"].write_text(json.dumps({"summary": text_b_cooking}))

    files["c.html"] = input_dir / "c.html"
    files["c.html"].write_text(
        "<html><body><article><h1>Caatinga</h1>"
        f"<p>{text_c_geography}</p></article></body></html>"
    )

    files["short.txt"] = input_dir / "short.txt"
    files["short.txt"].write_text("too short")  # rejected by length filter

    return files


class TestPipelineE2E:
    def test_full_run(self, tmp_path):
        input_dir = tmp_path / "in"
        output_dir = tmp_path / "out"
        _mk_corpus(input_dir)

        config = PipelineConfig(
            input_dir=input_dir,
            output_dir=output_dir,
            show_progress=False,
            filter_config=FilterConfig(min_chars=200),
        )
        report = Pipeline(config, language_predictor=MockLangPredictor()).run()

        # 5 input files. a_dup is removed by pre-dedup, short is removed by filter.
        assert report.input_files == 5
        assert report.pre_dedup_kept == 4  # a_dup gone
        assert report.parsed == 4
        assert report.filter_passed == 3  # short.txt rejected by length
        assert report.filter_rejected == {"length": 1}

        # Three remaining docs are unrelated enough to survive post-dedup.
        assert report.post_dedup_kept == 3
        assert report.post_dedup_removed == 0

        assert report.shards_written == 1
        assert report.total_chars_written > 0
        assert report.duration_seconds > 0

        # Output artifacts present.
        assert (output_dir / "shard-0000.parquet").exists()
        assert (output_dir / MANIFEST_FILENAME).exists()

    def test_parquet_content_matches(self, tmp_path):
        input_dir = tmp_path / "in"
        output_dir = tmp_path / "out"
        _mk_corpus(input_dir)

        config = PipelineConfig(
            input_dir=input_dir,
            output_dir=output_dir,
            show_progress=False,
            filter_config=FilterConfig(min_chars=200),
        )
        Pipeline(config, language_predictor=MockLangPredictor()).run()

        table = pq.read_table(output_dir / "shard-0000.parquet")
        assert table.num_rows == 3

        sources = set(table["source_path"].to_pylist())
        # short.txt and a_dup.txt should be absent.
        assert "short.txt" not in sources
        assert "a_dup.txt" not in sources
        # a.txt, b.json, c.html should be present.
        assert sources == {"a.txt", "b.json", "c.html"}

        # Language column populated by the LID step.
        languages = set(table["language"].to_pylist())
        assert languages == {DEFAULT_PT_LABEL}

    def test_disable_filter(self, tmp_path):
        input_dir = tmp_path / "in"
        output_dir = tmp_path / "out"
        _mk_corpus(input_dir)

        config = PipelineConfig(
            input_dir=input_dir,
            output_dir=output_dir,
            show_progress=False,
            enable_filter=False,
        )
        # Without filter, no LID needed.
        report = Pipeline(config).run()

        # All 4 post-pre-dedup files keep going (including short.txt).
        assert report.parsed == 4
        assert report.filter_passed == 0  # filter disabled
        assert report.post_dedup_kept == 4

    def test_disable_pre_dedup(self, tmp_path):
        input_dir = tmp_path / "in"
        output_dir = tmp_path / "out"
        _mk_corpus(input_dir)

        config = PipelineConfig(
            input_dir=input_dir,
            output_dir=output_dir,
            show_progress=False,
            enable_pre_dedup=False,
            enable_post_dedup=False,
            filter_config=FilterConfig(min_chars=200),
        )
        report = Pipeline(config, language_predictor=MockLangPredictor()).run()

        # a_dup survives pre-dedup; post-dedup is also off so duplicates stay.
        assert report.pre_dedup_kept == 5
        assert report.parsed == 5
        assert report.post_dedup_kept == 4  # short rejected by filter only

    def test_unsupported_format_recorded(self, tmp_path):
        input_dir = tmp_path / "in"
        output_dir = tmp_path / "out"
        input_dir.mkdir()

        # Create a binary file with no registered MIME parser.
        (input_dir / "blob.bin").write_bytes(b"\x00\x01\x02\x03" * 1024)

        config = PipelineConfig(
            input_dir=input_dir,
            output_dir=output_dir,
            show_progress=False,
            enable_filter=False,
        )
        report = Pipeline(config).run()

        # The file is detected but no parser exists -> failure recorded.
        assert report.input_files == 1
        assert report.parsed == 0
        assert len(report.parse_failures) == 1
        # Either detect or registry stage; both are valid.
        assert report.parse_failures[0].stage in {"detect", "registry"}
