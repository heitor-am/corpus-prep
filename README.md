# corpus-prep

Pipeline open-source de preparação de corpus para treinamento e fine-tuning de LLMs em português brasileiro.

Ingere arquivos heterogêneos (PDF, DOCX, PPTX, HTML, imagens, texto) e produz shards Parquet prontos para tokenização, com extração via OCR local, normalização de encoding, filtragem por idioma e deduplicação.

> Projeto da disciplina **Tópicos em IA / DC-CCN072 — UFPI** (atividade 03), desenhado para sobreviver à matéria como showcase de portfólio.

## Status

Em desenvolvimento. Ver [`PRD.md`](./PRD.md) para a especificação completa.

## Stack

| Camada | Ferramenta |
|---|---|
| MIME detection | Magika |
| PDF nativo | PyMuPDF4LLM |
| PDF escaneado / DOCX / PPTX / IMG | Docling |
| HTML | Trafilatura |
| Encoding fix | ftfy |
| Language ID | GlotLID v3 |
| Deduplicação | text-dedup (exact + MinHash) |
| Output | Parquet (pyarrow) |
| Exploração | DuckDB |

Sem APIs pagas. Sem serviços de terceiros. Roda em CPU. Detalhes em [`PRD.md` §5](./PRD.md#5-stack-tecnológica).

## Quickstart

```bash
# 1. Setup
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# 2. Download the sample corpus (PT-BR diarios oficiais) into data/raw/
./scripts/fetch_sample_corpus.sh

# 3. (Optional) download the GlotLID v3 model used by the language filter
./scripts/download_glotlid.sh

# 4. Run the pipeline (CLI lands in M6)
# corpus-prep ingest data/raw -o data/corpus
# corpus-prep explore data/corpus

# Until M6 ships, drive the pipeline programmatically:
python -c "
from pathlib import Path
from corpus_prep.pipeline import run_pipeline, PipelineConfig
config = PipelineConfig(
    input_dir=Path('data/raw'),
    output_dir=Path('data/corpus'),
)
print(run_pipeline(config))
"
```

The fetcher pulls from a public Google Drive folder via `gdown` — no OAuth required as long as the folder is shared with "Anyone with the link". Override the source by exporting `DRIVE_URL` before running. Drive applies per-IP rate limits on public-folder downloads; the script retries up to five times with backoff and `gdown` skips files already present, so re-running picks up where it left off.

## Cobertura da atividade 03

| Item enunciado | Onde |
|---|---|
| Q1 — Trafilatura | `src/corpus_prep/parsers/html_parser.py` |
| Q2 — Parquet | `src/corpus_prep/shard.py` |
| Q3 — RefinedWeb | `docs/refinedweb-summary.md` |
| Q4 — ftfy | `src/corpus_prep/normalize.py` + `notebooks/q4_ftfy_examples.ipynb` |
| Q5 — Downstream | seção abaixo |
| Q6 — Dedup pré/pós | `src/corpus_prep/dedup.py` |
| Q7 — OCR + formatos | `src/corpus_prep/parsers/` (9 formatos) |
| Q8 — DuckDB SQL | `notebooks/q8_duckdb_explore.ipynb` |

## Conceitos

> A elaborar nos milestones finais. Por enquanto:

- **Trafilatura:** biblioteca de extração de conteúdo principal de páginas web. Remove boilerplate (menus, headers, ads) e retorna apenas o texto relevante. Usada no pipeline do dataset RefinedWeb (Falcon LLM) para limpar dumps do Common Crawl.
- **Apache Parquet:** formato de armazenamento colunar otimizado para leitura analítica. Compressão eficiente, schema embutido, leitura seletiva de colunas. Padrão do HuggingFace Datasets.
- **RefinedWeb:** dataset de ~5T tokens, 100% web filtrada, criado pela TII (Abu Dhabi) para treinar Falcon LLM. Demonstrou que dados web cuidadosamente filtrados podem igualar ou superar corpora curados (The Pile, C4) em benchmarks downstream.
- **Mojibake / ftfy:** texto corrompido por encoding incorreto (`Ã©` em vez de `é`). `ftfy` detecta e reverte essas corrupções.
- **Aplicações downstream:** tarefas finais para as quais um modelo pré-treinado é adaptado (classificação de sentimento, NER, QA, sumarização, tradução, geração de código).

## Referências

- [PRD completo](./PRD.md)
- [Build a Large Language Model From Scratch — Raschka, 2024](https://www.manning.com/books/build-a-large-language-model-from-scratch)
- [The RefinedWeb Dataset for Falcon LLM — Penedo et al., 2023](https://arxiv.org/abs/2306.01116)

## Licença

[MIT](./LICENSE).
