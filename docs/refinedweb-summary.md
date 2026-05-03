# RefinedWeb — summary

> Penedo, Malartic, Hesslow, Cojocaru, Cappelli, Alobeidli, Pannier, Almazrouei, Launay (TII Abu Dhabi). *The RefinedWeb Dataset for Falcon LLM: Outperforming Curated Corpora with Web Data, and Web Data Only*. NeurIPS 2023. [arXiv:2306.01116](https://arxiv.org/abs/2306.01116).

## What it is

**RefinedWeb** is a 5-trillion-token English corpus distilled from the Common Crawl by the Technology Innovation Institute (Abu Dhabi). It powered the original Falcon family (7B / 40B / 180B) and a 600 GB sample is publicly available on the Hugging Face Hub.

The headline contribution is methodological, not the dataset itself: the authors show that **carefully filtered web data alone** can match or beat the heavily curated corpora (The Pile, C4, BookCorpus, Wikipedia mixes) that previously defined the LLM-training playbook.

## The pipeline (Macrodata Refinement)

The paper introduces *Macrodata Refinement* (MDR), a five-stage pipeline that turns raw Common Crawl WARCs into training-ready text:

1. **URL filtering** — block-list of adult/spam/aggregator domains plus a heuristic against "low-quality" URLs (excessive subdomains, very long paths, tracking parameters).
2. **Text extraction** — main-content extraction with **Trafilatura**. Drops navigation, ads, footers, comment threads.
3. **Language identification** — fastText classifier (`lid.176`); documents whose top-1 confidence is below 0.65 are dropped.
4. **Repetition / quality filtering** — heuristics adapted from MassiveText (Gopher): symbol-to-word ratio, repeated line ratio, ellipsis fraction, etc.
5. **Deduplication** — three layers: exact-match line dedup, **MinHash LSH** at the document level (Jaccard 0.8), and an internal long-substring filter that removes copy-pasted blocks.

The pipeline is single-pass and shard-parallelizable; the authors run it on Common Crawl dumps from 2008 to 2023.

## The experiment

To validate the "web-only" claim the authors train multiple Falcon-1B and Falcon-7B variants on:

- **RefinedWeb** alone
- The Pile
- C4
- OSCAR-22.01
- A "curated" mix mirroring GPT-3 and PaLM data recipes

All variants share an identical architecture, optimizer, vocabulary, and token budget. They evaluate on **zero-shot downstream tasks** (HellaSwag, PIQA, ARC-Easy/Challenge, BoolQ, OpenBookQA, Winogrande, etc.) and on **language-modeling perplexity** on held-out web text.

## The result

RefinedWeb-trained models **match or beat** every curated baseline on aggregate downstream accuracy, even though the comparison corpora include high-prestige sources like books and arXiv. Falcon-7B trained on RefinedWeb alone, for example, surpasses LLaMA-7B trained on the original LLaMA mix (which itself was a curated multi-source recipe).

## Why it matters for `corpus-prep`

RefinedWeb is the reason the stack in this repo looks the way it does:

- **Trafilatura** for HTML extraction — the same library used by RefinedWeb itself.
- **fastText / GlotLID** for language ID — same lineage; we swap in GlotLID v3 for better PT-BR coverage.
- **MinHash LSH at Jaccard 0.8** for post-dedup — the threshold ships as the default in `corpus-prep.dedup.dedup_documents`.
- **Quality heuristics** — the length / repetition / char-ratio filters in `corpus_prep.filter` are direct analogues of the MassiveText rules MDR adopts.

The takeaway for any domain-specific corpus is the same as the paper's headline finding: **filtering matters more than provenance**. A corpus of Brazilian official journals is not "books and Wikipedia," but with the same MDR-shaped pipeline (encoding fix, language ID, dedup, quality filters) it produces clean training data without any curated supplementation.

## References

- Paper: <https://arxiv.org/abs/2306.01116>
- HuggingFace dataset card: <https://huggingface.co/datasets/tiiuae/falcon-refinedweb>
- Trafilatura: <https://github.com/adbar/trafilatura>
- HuggingFace `datatrove` (open-source MDR-style pipeline that descends from this paper): <https://github.com/huggingface/datatrove>
