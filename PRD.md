# PRD — corpus-prep

> Pipeline open-source de preparação de corpus para treinamento e fine-tuning de LLMs, em PT-BR. Disciplina **Tópicos em IA / DC-CCN072 — UFPI**, atividade 03.

---

## 1. Visão geral

`corpus-prep` é uma biblioteca + CLI que ingere arquivos heterogêneos (PDF, DOCX, PPTX, HTML, imagens, texto), produz texto limpo, deduplicado, filtrado por idioma e exporta como shards Parquet prontos para tokenização e treinamento de LLMs.

O pipeline executa estritamente local, sem APIs pagas, sem serviços de terceiros. Roda em CPU. Cobre os requisitos da atividade 03 e foi desenhado para sobreviver à matéria como showcase de portfólio.

---

## 2. Contexto e motivação

A atividade 03 da disciplina DC/CCN072 pede que os grupos:

1. Pesquisem conceitos de preparação de dados (Trafilatura, Parquet, RefinedWeb, ftfy, downstream).
2. Implementem deduplicação pré e pós-processada.
3. Estendam um pipeline de extração existente com OCR e formatos adicionais.
4. Explorem dados em Parquet com SQL (DuckDB).

A solução padrão seria um notebook único reproduzindo a palestra. Este projeto vai além: empacota o pipeline como biblioteca reutilizável com decisões de arquitetura justificadas, output em formato padrão da indústria (HuggingFace Datasets) e cobertura completa de formatos típicos de domínio brasileiro (diários oficiais, documentos administrativos).

A inspiração arquitetural vem do [DocSmith](https://github.com/heitor-am/docsmith) (Registry Pattern + BaseParser), mas o stack interno foi totalmente substituído por bibliotecas open-source locais.

---

## 3. Escopo

### 3.1 Dentro do escopo

| Capacidade | Atende |
|---|---|
| Detecção de MIME via Magika | Q7 |
| Extração de PDF nativo (texto selecionável) | Q7 |
| Extração de PDF escaneado via OCR | Q7 |
| Extração de DOCX, PPTX, HTML, imagens | Q7 |
| Extração de TXT, MD, CSV, JSON | Q7 |
| Correção de mojibake/encoding | Q4 |
| Filtragem por idioma (PT-BR) | extra |
| Deduplicação exact (SHA-256) — pré-processamento | Q6 |
| Deduplicação MinHash LSH — pós-processamento | Q6 |
| Output em Parquet com schema explícito | Q2 |
| Notebooks de exploração com DuckDB | Q8 |
| CLI ergonômica (`corpus-prep ingest data/raw -o data/corpus`) | extra |
| Documentação dos conceitos teóricos no README | Q1, Q3, Q5 |

### 3.2 Fora do escopo (e por quê)

| Excluído | Motivo |
|---|---|
| Áudio / vídeo (Whisper) | Decisão do usuário; reduz dependências e GPU |
| Tokenização (tiktoken / sliding windows) | Pertence à atividade 01; output Parquet alimenta esse pipeline downstream |
| Embeddings, indexing, busca semântica | Não é training prep; é RAG |
| Crawling / web scraping | Pertence à atividade 04 |
| Quality classifiers ML (FineWeb-Edu, BERT) | Inglês only; sem alternativa calibrada para PT-BR no escopo |
| KenLM perplexity filter | Treinar modelo PT seria sub-projeto separado; v1 sem isso |
| Distribuição (Slurm, Ray, Spark) | Escala de centenas de MB cabe single-node |
| Streaming / WebDataset | Parquet basta; otimização prematura |

---

## 4. Objetivos

| Objetivo | Métrica de sucesso |
|---|---|
| Pipeline executável end-to-end | `corpus-prep ingest data/raw -o data/corpus` produz Parquet sem erro em corpus de teste |
| Cobertura de formatos | ≥ 9 formatos (PDF nativo, PDF escaneado, DOCX, PPTX, HTML, IMG, TXT, MD, CSV, JSON) |
| Qualidade de OCR | Page-level WER ≤ 5% em PDFs de diários oficiais de teste |
| Performance | Corpus de 100 MB processado em < 30 min num laptop CPU 8-core |
| Determinismo | Re-execução produz output idêntico (hashes batem) |
| Cobertura de testes | ≥ 70% nos módulos `parsers/`, `dedup.py`, `normalize.py` |
| Reprodutibilidade | `pip install -e .` + `pytest` passa em máquina limpa |
| Documentação | README cobre Q1, Q3, Q5 conceitualmente; PRD detalha decisões |

---

## 5. Stack tecnológica

Decisões locked-in. Cada escolha justificada vs alternativa avaliada (ver pesquisa em `docs/research-notes.md`).

| Camada | Ferramenta | Versão mínima | Licença | Por quê |
|---|---|---|---|---|
| MIME detection | `magika` | 0.5+ | Apache-2.0 | +22-47% F1 vs python-magic; modelo <1MB |
| PDF nativo | `pymupdf4llm` (sobre PyMuPDF) | 0.0.17+ | AGPL-3.0 | Output markdown-ready, instantâneo em CPU |
| PDF escaneado / DOCX / PPTX / IMG | `docling` | 2.0+ | MIT | IBM, multi-formato, OCR embutido (EasyOCR/RapidOCR backend), CPU funciona |
| HTML | `trafilatura` | 1.12+ | Apache-2.0 | F1 0.945 (SOTA), referência de Q1 do enunciado |
| Encoding fix | `ftfy` | 6.3+ | Apache-2.0 | Padrão de fato, exigido por Q4 |
| Language ID | `fasttext` + GlotLID v3 model | — | MIT (lib) / research (model) | 2102 idiomas, supera lid.176 em PT-BR |
| Deduplicação | `text-dedup` | git+main (não publicado em PyPI estável) | Apache-2.0 | Inclui exact + MinHash LSH numa só lib |
| Output | `pyarrow` | 18+ | Apache-2.0 | Parquet, zstd, schema; integra com `datasets` HF |
| Exploração SQL | `duckdb` | 1.1+ | MIT | Zero-config, lê Parquet direto |
| CLI | `typer` | 0.12+ | MIT | Wrapper sobre Click, type hints como subcomandos |
| Schemas | `pydantic` v2 | 2.9+ | MIT | Validação de config + ParseResult |
| Logging | `structlog` | 24+ | Apache-2.0 / MIT | Logs estruturados, pareia com DuckDB se preciso |
| Progress bar | `rich` | 13+ | MIT | Progress + tabelas no terminal |

> **Nota sobre PyMuPDF4LLM (AGPL):** usado apenas como dependência *runtime*, não distribuído junto. Para um repo MIT público, a AGPL do PyMuPDF se aplica ao **uso da biblioteca**, não ao código que a importa. É equivalente a usar PostgreSQL (PostgreSQL License) num app MIT — não contamina. Documentar essa decisão no README.
>
> **Alternativa 100% MIT:** se preocupação aumentar, trocar por `pdfplumber` (MIT) — perde qualidade em PDFs complexos mas resolve a licença. Decisão diferida para milestone 2.

### Dev dependencies

`pytest`, `pytest-cov`, `ruff` (lint+format), `mypy --strict`, `pre-commit`.

### Python version

`>= 3.11`. Pattern matching, `tomllib` na stdlib, type aliases nativos.

---

## 6. Arquitetura

### 6.1 Fluxo de dados

```
                    ┌───────────────┐
                    │  data/raw/    │  Arquivos heterogêneos
                    └───────┬───────┘
                            │
                  ┌─────────▼──────────┐
                  │  Pre-dedup hash    │  exact dedup por SHA-256
                  │  (Q6 pré)          │  remove duplicatas binárias
                  └─────────┬──────────┘
                            │
                    ┌───────▼───────┐
                    │   Magika      │  detecta MIME real
                    └───────┬───────┘
                            │
                ┌───────────▼────────────┐
                │   ParserRegistry       │
                │   roteamento por MIME  │
                └─────┬──────────────┬───┘
                      │              │
        ┌─────────────┴──┐    ┌──────┴───────┐
        │ PDFNativeParser│    │ DoclingParser│  (DOCX/PPTX/IMG/PDF escaneado)
        │ (PyMuPDF4LLM)  │    │              │
        └────────┬───────┘    └──────┬───────┘
                 │     ┌──────────────┤
                 │     │ HTMLParser   │  (Trafilatura)
                 │     └──────┬───────┘
                 │            │     ┌────────────────┐
                 │            │     │ TextLikeParser │  (TXT/MD/CSV/JSON)
                 │            │     └────────┬───────┘
                 ▼            ▼              ▼
                    ┌─────────────────┐
                    │   ParseResult   │  text + metadata
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   normalize.py  │  ftfy + whitespace + control chars
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   filter.py     │  GlotLID PT, min_length, etc
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Post-dedup     │  MinHash LSH (Jaccard ≥ 0.8)
                    │  (Q6 pós)       │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   shard.py      │  Parquet shards, ~256MB cada
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  data/corpus/   │
                    │   shard-0000.parquet
                    │   shard-0001.parquet
                    │   manifest.json
                    └─────────────────┘
```

### 6.2 Estrutura de pastas

```
corpus-prep/
├── PRD.md                              ← este arquivo
├── README.md                           ← overview público + Q1, Q3, Q5
├── LICENSE                             ← MIT
├── pyproject.toml                      ← deps, metadata, scripts entry
├── .gitignore                          ← data/, .venv/, __pycache__
├── .pre-commit-config.yaml             ← ruff + mypy
│
├── src/corpus_prep/
│   ├── __init__.py
│   ├── cli.py                          ← typer commands (ingest, explore, etc)
│   ├── pipeline.py                     ← orquestrador linear
│   ├── config.py                       ← pydantic Settings
│   ├── schemas.py                      ← ParseResult, Document, ShardMeta
│   ├── detect.py                       ← Magika wrapper
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base.py                     ← BaseParser ABC
│   │   ├── registry.py                 ← @register decorator + lookup
│   │   ├── pdf_native.py               ← PyMuPDF4LLM
│   │   ├── docling_parser.py          ← Docling (PDF scan, DOCX, PPTX, IMG)
│   │   ├── html_parser.py             ← Trafilatura
│   │   └── textlike.py                 ← TXT/MD/CSV/JSON triviais
│   ├── normalize.py                    ← ftfy + Unicode normalization
│   ├── filter.py                       ← GlotLID + length + heurísticas
│   ├── dedup.py                        ← exact (sha256) + MinHash LSH
│   ├── shard.py                        ← Parquet writer + manifest
│   └── utils/
│       ├── hashing.py                  ← SHA-256 streaming
│       └── io.py                       ← read/write helpers
│
├── tests/
│   ├── conftest.py                     ← fixtures (sample files)
│   ├── fixtures/                       ← mini corpus (~5MB) versionado
│   │   ├── nativo.pdf
│   │   ├── escaneado.pdf
│   │   ├── teste.docx
│   │   ├── slides.pptx
│   │   ├── pagina.html
│   │   └── imagem.png
│   ├── test_detect.py
│   ├── test_parsers.py
│   ├── test_normalize.py
│   ├── test_filter.py
│   ├── test_dedup.py
│   ├── test_shard.py
│   └── test_pipeline_e2e.py
│
├── notebooks/
│   ├── q4_ftfy_examples.ipynb          ← demo Q4
│   ├── q6_dedup_walkthrough.ipynb      ← visualizar dedup
│   ├── q7_format_coverage.ipynb        ← rodar pipeline em corpus exemplo
│   └── q8_duckdb_explore.ipynb         ← queries SQL em Parquet
│
├── docs/
│   ├── research-notes.md               ← histórico das decisões + benchmarks
│   ├── architecture.md                 ← diagrama detalhado + decision records
│   └── refinedweb-summary.md           ← Q3 conceitual
│
└── scripts/
    ├── download_glotlid.sh             ← baixa modelo GlotLID v3
    └── make_test_corpus.py             ← gera fixtures sintéticas
```

---

## 7. Especificação por módulo

### 7.1 `detect.py` — MIME detection

**Responsabilidade:** dado um path, retornar MIME type real (não confiar em extensão).

**API:**
```python
def detect_mime(path: Path) -> str:
    """Retorna MIME type usando Magika. Fallback para 'application/octet-stream'."""
```

**Comportamento:**
- Lê primeiros 4KB para detecção (Magika não precisa do arquivo todo)
- Cacheia o `Magika()` instance globalmente (init é caro)
- Score < 0.7 → retorna `application/octet-stream` (forçará erro no Registry)

**Testes:** detectar PDF, DOCX, PPTX, HTML, PNG, MP3 (mesmo que não processado), TXT.

---

### 7.2 `parsers/`

#### 7.2.1 `base.py` — interface

```python
from abc import ABC, abstractmethod
from pathlib import Path
from corpus_prep.schemas import ParseResult

class BaseParser(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def supported_mime_types(self) -> list[str]: ...

    @abstractmethod
    def parse(self, path: Path) -> ParseResult: ...
```

Síncrono (vs DocSmith que era async — não precisa aqui, executor processa em paralelo).

#### 7.2.2 `registry.py` — registro + lookup

```python
_registry: dict[str, type[BaseParser]] = {}

def register(*mime_types: str):
    def decorator(cls: type[BaseParser]):
        for mime in mime_types:
            _registry[mime] = cls
        return cls
    return decorator

def get_parser(mime: str) -> BaseParser:
    if mime not in _registry:
        raise UnsupportedFormatError(mime)
    return _registry[mime]()
```

Auto-import dos parsers via `parsers/__init__.py` para popular registry.

#### 7.2.3 `pdf_native.py` — PDF com texto selecionável

- Backend: `pymupdf4llm.to_markdown(path)`
- Heurística pré-OCR: `len(text) / num_pages < 100` → roteia para Docling
- Output: markdown como `text`, `pages` count, `extraction_method="pymupdf4llm"`

#### 7.2.4 `docling_parser.py` — multi-formato com OCR

- Backend: `docling.DocumentConverter().convert(path)`
- MIME types: PDF (escaneado), DOCX, PPTX, PNG, JPEG, TIFF
- Configurar OCR engine: EasyOCR com `lang=["pt"]`
- Output: `result.document.export_to_markdown()` como `text`

#### 7.2.5 `html_parser.py` — extração de conteúdo principal

- Backend: `trafilatura.extract(html, include_comments=False, include_tables=True)`
- Fallback: se retornar `None`, tentar `extract` com `favor_recall=True`
- MIME types: `text/html`

#### 7.2.6 `textlike.py` — formatos texto triviais

- TXT: read direto + decode com `chardet` se UTF-8 falhar
- MD: read direto (já é texto)
- CSV: `csv.DictReader` → linhas como "col1: val1 | col2: val2"
- JSON: `json.dumps(obj, indent=2, ensure_ascii=False)`

---

### 7.3 `normalize.py`

**Responsabilidade:** corrigir encoding e padronizar texto.

```python
def normalize(text: str) -> str:
    text = ftfy.fix_text(text)
    text = unicodedata.normalize("NFC", text)
    text = _remove_control_chars(text)
    text = _collapse_whitespace(text)
    return text.strip()
```

**Operações:**
1. ftfy.fix_text — mojibake (`Ã©` → `é`)
2. NFC normalization — combina caracteres compostos
3. Remove caracteres de controle (\x00-\x08, \x0B-\x1F) exceto \n e \t
4. Colapsa whitespace múltiplo (regex `\s+` → ` `, mas preserva newlines duplos)

**Testes:** Q4 do enunciado vira casos de teste explícitos.

---

### 7.4 `filter.py` — quality + language

```python
def is_valid(doc: Document, config: FilterConfig) -> tuple[bool, str | None]:
    """Retorna (mantém, motivo_descartado)."""
```

**Filtros aplicados em ordem:**
1. **Length:** `len(text) < config.min_chars` (default 200) → descarta
2. **Language:** GlotLID prediz idioma; se != `por_Latn` com confiança > 0.5 → descarta
3. **Repetition:** se `len(set(words)) / len(words) < 0.1` → descarta (texto quase tudo igual)
4. **Char ratio:** se `non_alpha_ratio > 0.5` → descarta (provavelmente OCR ruim)

Cada filtro registra estatística. Manifest final reporta quantos descartes por motivo.

---

### 7.5 `dedup.py`

#### Pré-dedup (binário)

```python
def dedup_files(paths: list[Path]) -> list[Path]:
    """Remove paths cujo SHA-256 já apareceu. Stream-hash 64KB chunks."""
```

#### Pós-dedup (semântico via MinHash)

```python
def dedup_documents(docs: list[Document], jaccard_threshold: float = 0.8) -> list[Document]:
    """
    Usa text-dedup MinHashLSH:
    - num_perm = 128
    - n-grams = 5 (palavras)
    - threshold = 0.8
    Retorna lista deduplicada, mantendo o primeiro de cada cluster.
    """
```

**Implementação:** library `text-dedup` com backend `datasketch`. Persiste índice em disco (`data/.dedup-index/`) para re-execução incremental.

---

### 7.6 `shard.py`

```python
def write_shards(
    docs: Iterator[Document],
    output_dir: Path,
    target_shard_mb: int = 256,
) -> ShardManifest:
```

**Schema Parquet:**

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | string | UUID v7 (sortable) |
| `text` | large_string | Conteúdo extraído + normalizado |
| `source_path` | string | Caminho relativo ao input dir |
| `mime` | string | Detectado por Magika |
| `parser` | string | Nome do parser usado |
| `extracted_at` | timestamp[us, UTC] | Timestamp da extração |
| `char_count` | int32 | Contagem de chars |
| `language` | string | Código GlotLID (`por_Latn`) |
| `language_confidence` | float32 | Confiança LID |
| `sha256` | string | Hash do binário original |
| `metadata` | map<string, string> | Extras do parser (page_count, tables_count etc) |

**Compressão:** zstd level 3 (boa relação tamanho/velocidade).

**Manifest (`manifest.json`):** lista de shards, total de documentos, total de bytes, schema version, config usada na execução, timestamp.

---

### 7.7 `pipeline.py` — orquestrador

```python
class Pipeline:
    def __init__(self, config: PipelineConfig): ...

    def run(self, input_dir: Path, output_dir: Path) -> RunReport:
        # 1. Discovery: rglob de input_dir
        # 2. Pre-dedup: sha256 dedup
        # 3. Parse: paralelo via ProcessPoolExecutor
        #    - Skipa se MIME unsupported (loga warning)
        #    - Skipa se parser falha (loga error com path)
        # 4. Normalize: aplica em cada doc
        # 5. Filter: aplica filtros, registra estatísticas
        # 6. Post-dedup: MinHash LSH
        # 7. Shard: escreve Parquet
        # 8. Report: imprime resumo + retorna RunReport
```

**Concorrência:** `ProcessPoolExecutor(max_workers=os.cpu_count() - 1)`. Cada worker processa 1 arquivo. Resultados acumulados na main thread.

**Resilência:** falha em 1 arquivo NÃO derruba o pipeline. Log estruturado com `path`, `parser`, `error_type`, `traceback`. Manifest reporta lista de falhas.

---

### 7.8 `cli.py`

```bash
corpus-prep ingest data/raw -o data/corpus [--min-lang-confidence 0.5] [--shard-size 256]
corpus-prep explore data/corpus              # abre DuckDB shell pré-conectado
corpus-prep stats data/corpus                # imprime tabela de stats do manifest
corpus-prep dedup data/corpus -o data/dedup  # re-aplica dedup standalone
```

Implementação com `typer`. Help auto-gerado.

---

## 8. Schemas de dados (pydantic)

```python
class ParseResult(BaseModel):
    text: str
    parser_name: str
    char_count: int
    page_count: int | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

class Document(BaseModel):
    id: UUID
    text: str
    source_path: Path
    mime: str
    parser: str
    sha256: str
    language: str | None = None
    language_confidence: float | None = None
    char_count: int
    extracted_at: datetime
    metadata: dict[str, str]

class FilterStats(BaseModel):
    total: int
    kept: int
    rejected_by_length: int
    rejected_by_language: int
    rejected_by_repetition: int
    rejected_by_char_ratio: int

class RunReport(BaseModel):
    input_files: int
    deduplicated_files: int
    parsed: int
    parse_failures: list[ParseFailure]
    filter_stats: FilterStats
    post_dedup_kept: int
    shards_written: int
    total_chars: int
    duration_seconds: float
```

---

## 9. Mapeamento atividade 03 → entregas

| Item enunciado | Entrega no repo |
|---|---|
| Q1 — Trafilatura | `README.md` seção "Conceitos"; uso real em `parsers/html_parser.py` |
| Q2 — Parquet | `README.md` + `shard.py` + `notebooks/q8_duckdb_explore.ipynb` |
| Q3 — RefinedWeb | `docs/refinedweb-summary.md` (~500 palavras + referência ao paper) |
| Q4 — ftfy | `normalize.py` + `notebooks/q4_ftfy_examples.ipynb` (com casos de mojibake do enunciado) |
| Q5 — Downstream | `README.md` seção "Casos de uso downstream" |
| Q6 — Dedup pré/pós | `dedup.py` (`dedup_files` + `dedup_documents`) + `notebooks/q6_dedup_walkthrough.ipynb` |
| Q7 — OCR + formatos | `parsers/` (9 formatos: PDF nativo, PDF scan, DOCX, PPTX, IMG, HTML, TXT, MD, CSV, JSON) + `notebooks/q7_format_coverage.ipynb` |
| Q8 — DuckDB SQL | `notebooks/q8_duckdb_explore.ipynb` + comando `corpus-prep explore` |

---

## 10. Fases de implementação

### Milestone 0 — Setup (0.5 dia)

- `pyproject.toml`, `LICENSE` MIT, `.gitignore`, `README.md` skeleton
- `pre-commit` com ruff + mypy
- CI mínima (GitHub Actions: lint + test em 3.11/3.12)
- Estrutura de pastas vazia conforme §6.2

### Milestone 1 — Core parsers (1.5 dias)

- `schemas.py` (ParseResult, Document)
- `parsers/base.py` + `parsers/registry.py`
- `parsers/textlike.py` (TXT, MD, CSV, JSON)
- `parsers/pdf_native.py` (PyMuPDF4LLM)
- `parsers/html_parser.py` (Trafilatura)
- Testes unitários com fixtures pequenas

### Milestone 2 — Docling integration (1 dia)

- `parsers/docling_parser.py` (PDF scan, DOCX, PPTX, IMG)
- Configuração de EasyOCR backend para PT
- Heurística de roteamento PDF nativo → Docling
- Teste com PDF escaneado real (extrair de `studies/ufpi/topics-in-ai/files/`)

### Milestone 3 — Detect + normalize + filter (1 dia)

- `detect.py` com Magika
- `normalize.py` com ftfy + unicode
- `filter.py` com GlotLID
- Script `scripts/download_glotlid.sh`
- Testes de cada módulo isolado

### Milestone 4 — Dedup (1 dia)

- `dedup.py` exact (SHA-256 streaming)
- `dedup.py` MinHash LSH com `text-dedup`
- Notebook Q6 demonstrando ambos
- Teste com casos de duplicatas exatas e near-duplicates

### Milestone 5 — Shard + pipeline (1 dia)

- `shard.py` com schema Parquet
- `pipeline.py` orquestrando tudo
- Manifest JSON
- Teste E2E com fixtures

### Milestone 6 — CLI + notebooks (0.5 dia)

- `cli.py` com typer
- 4 notebooks (Q4, Q6, Q7, Q8)
- README final com seções conceituais (Q1, Q3, Q5)
- `docs/refinedweb-summary.md`

### Milestone 7 — Polish (0.5 dia)

- Ajustes de docstrings
- Cobertura de testes ≥ 70%
- Benchmark em corpus real (medir tempo, qualidade)
- Tag v0.1.0 + release notes

**Total estimado:** 6 dias úteis. Em paralelo a aulas, ~2 semanas calendário.

---

## 11. Estratégia de testes

### Fixtures

`tests/fixtures/` versiona corpus mini (~5MB total):
- `nativo.pdf` — PDF criado a partir de markdown (texto selecionável)
- `escaneado.pdf` — render de imagem em PDF (força OCR)
- `teste.docx`, `slides.pptx` — gerados via python-docx, python-pptx
- `pagina.html` — snapshot real de uma página com boilerplate
- `imagem.png` — print de texto para OCR
- `mojibake.txt` — texto com encoding quebrado para Q4
- `duplicata-exata.txt`, `near-duplicate.txt` — para Q6

Script `scripts/make_test_corpus.py` regenera fixtures sintéticas.

### Níveis

| Nível | Cobertura |
|---|---|
| Unit | Cada módulo isolado, mocks externos quando possível |
| Integration | Parser real → ParseResult → normalize → filter |
| E2E | `pipeline.run(fixtures/, output/)` produz Parquet válido com counts esperados |

### Métricas mínimas

- ≥ 70% line coverage em `parsers/`, `dedup.py`, `normalize.py`
- E2E test passa em < 60s (sem rodar OCR pesado em CI)
- OCR-heavy tests marcados com `@pytest.mark.slow`, opt-in via flag

---

## 12. Riscos e questões em aberto

| Risco | Mitigação |
|---|---|
| Docling demora para baixar modelos no primeiro uso | Documentar no README + pre-cache em CI |
| GlotLID model file (~120MB) não cabe em git | `.gitignore` + script de download em `scripts/` |
| OCR de diários oficiais antigos pode ter qualidade ruim mesmo com Docling | Adicionar Surya como fallback opcional em milestone 8 (post-MVP) |
| AGPL do PyMuPDF4LLM via runtime gera dúvida | Documentar análise; oferecer flag `--no-pymupdf` que troca por pdfplumber |
| `text-dedup` não tem release estável em PyPI | Pinear commit hash em pyproject.toml; avaliar fork interno |
| Performance: ProcessPoolExecutor + Docling pode estourar RAM | Limitar `max_workers` e adicionar `--memory-limit` flag |

### Questões em aberto

1. **Corpus real para benchmark:** usar diários oficiais de Teresina (mesma fonte da atividade 04) ou Wikipedia-PT dump?
2. **Versionar fixtures de OCR:** PDFs escaneados são pesados. Gerar sintéticos via PIL ou commitar reais (~20MB)?
3. **Output JSONL além de Parquet:** vale o opt-in para debug ou Parquet basta?

---

## 13. Decisões registradas

| Decisão | Data | Razão |
|---|---|---|
| Docling sobre MinerU como driver multi-formato | 2026-05-03 | Licença MIT vs AGPL; repo será público |
| faster-whisper / áudio fora do escopo v1 | 2026-05-03 | Pedido explícito do usuário; reduz GPU |
| Pipeline síncrono (não async) | 2026-05-03 | Concorrência via ProcessPoolExecutor; menos cerimônia que asyncio |
| Output Parquet único formato em v1 | 2026-05-03 | Padrão HF Datasets; JSONL pode vir em v2 |
| `corpus-prep` como nome | 2026-05-03 | Genérico, não amarra a UFPI; sobreviverá ao curso |

---

## Referências

- [Build a Large Language Model From Scratch — Sebastian Raschka, 2024](https://www.manning.com/books/build-a-large-language-model-from-scratch)
- [The RefinedWeb Dataset for Falcon LLM — Penedo et al., 2023](https://arxiv.org/abs/2306.01116)
- [Docling — IBM](https://github.com/docling-project/docling)
- [Trafilatura](https://github.com/adbar/trafilatura)
- [text-dedup](https://github.com/ChenghaoMou/text-dedup)
- [Magika](https://github.com/google/magika)
- [GlotLID](https://github.com/cisnlp/GlotLID)
- [datatrove (referência arquitetural)](https://github.com/huggingface/datatrove)
- [HuggingFace Datasets — Parquet schema](https://huggingface.co/docs/datasets/about_arrow)
