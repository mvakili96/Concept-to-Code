# Grounded Interview Prep RAG

A local, source-grounded assistant that connects technical interview theory to targeted coding practice.

Technical interview preparation is fragmented: trusted explanations live in textbooks, while coding practice lives in a large problem bank that is difficult to prioritize. This project is being built to close that gap. It answers questions from a curated engineering library with page-level citations and is evolving toward recommending LeetCode coding problems that exercise the same transferable algorithmic patterns.

The goal is to help candidates move deliberately from concepts in computer vision, machine learning, NLP, system design, and data systems to coding exercises that reinforce the same reasoning skills.

## Project status

The core RAG pipeline and retrieval benchmark already support grounded answers to theoretical questions. Current development focuses on a separate workflow that connects those concepts to related LeetCode problems without changing the existing question-answering flow.

| Area | Status |
|---|---|
| Grounded single-turn question answering | Implemented |
| Conversational follow-ups and source memory | Implemented |
| Persistent hybrid retrieval and retrieval ablations | Implemented |
| Source-grounded retrieval benchmark | Implemented: 50 source-audited questions |
| Automated software tests | Planned: add unit, integration, and end-to-end tests for the pipeline and terminal workflows |
| Multi-turn conversation benchmark | Planned: create test conversations with follow-up questions and source changes |
| Multi-turn conversation evaluation | Planned: run the conversational pipeline on the new benchmark and report the results |
| `/related` direct LeetCode search | Built on the feature branch. Not yet on `master` |
| Match textbook concepts to LeetCode problems | Being implemented: retrieve textbook evidence, identify its coding patterns, and search LeetCode with those patterns |
| Recommendation-specific benchmark | Planned |

### Direction of development for LeetCode recommendations

On the `related-problem-retrieval` branch, an explicit command runs the new workflow in conversation mode:

```text
/related Hough transform in computer vision
```

The current baseline searches only the existing *LeetCode 4000 Problem Reference* chunks. It reuses query expansion, dense and BM25 retrieval, candidate deduplication, and cross-encoder reranking, then asks the language model for up to three grounded recommendations. Its prompt requires a clear relationship, citations, and an important difference from the original topic. It can return no recommendation instead of forcing a weak match.

The intended concept-to-practice flow is:

```text
technical topic
    -> retrieve grounded textbook evidence
    -> extract source terms and transferable coding patterns
    -> build a bridge query
    -> search only the LeetCode collection
    -> rerank by conceptual relationship
    -> explain the relationship and the differences with citations
```

The next milestone is the evidence-and-pattern bridge: retrieve the technical explanation first, ask Qwen for conservative structured pattern extraction, and use those patterns for LeetCode retrieval. Later work will add relevance thresholds, a recommendation benchmark with multiple acceptable answers and no-good-match cases, ablations, and conversation integration.

The first version continues to use the repository's ordinary LeetCode chunks. Problem-aware parsing will be introduced only if evaluation shows that overlapping or split chunks produce incomplete or duplicate recommendations.

## How the current pipeline works

| Component | Implementation |
|---|---|
| PDF ingestion | `pypdf` with one-based physical page metadata |
| Chunking | LangChain recursive text splitting with stable chunk IDs |
| Dense retrieval | MiniLM embeddings with FAISS IndexFlat or HNSW |
| Sparse retrieval | BM25 with optional Qwen-based query expansion |
| Candidate fusion | Chunk-ID deduplication across retrievers |
| Reranking | MiniLM cross-encoder |
| Generation | `Qwen2.5-7B-Instruct` with source and page citations |
| Conversation | Follow-up rewriting, in-memory history, and active-source state |
| Persistence | Reusable corpus, BM25, IndexFlat, and HNSW artifacts |
| Evaluation | Deterministic evidence-overlap measurement on a fixed benchmark |

IndexFlat performs exact nearest-neighbor search over every vector. HNSW navigates an approximate graph and trades a small amount of recall for faster search on larger indexes. Both modes return the configured top-k results.

A normal question written as `According to "<exact PDF filename>", ...` restricts retrieval to that source; otherwise, the full corpus is searched. On the feature branch, the `/related` workflow overrides this behavior and searches only the configured LeetCode source.

## Getting started

Create an environment and install the dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Place the source PDFs in `documents/`. The directory is intentionally git-ignored. The benchmark's expected filenames, hashes, and page counts are recorded in [`evaluation-data/corpus_manifest_v1.json`](evaluation-data/corpus_manifest_v1.json).

On the first run, set `indexing.mode` in [`config.yml`](config.yml) to `build`, then run:

```bash
python main.py
```

Build mode parses and chunks the corpus, constructs BM25 plus both FAISS indexes, saves them under the git-ignored `index-data/` directory, and then enters the configured interaction mode. After that initial build, change `indexing.mode` to `load` to reuse the saved artifacts. Changes to chunking, embeddings, BM25 construction, or HNSW construction require a rebuild. Query-time retrieval settings do not.

With `conversation.enabled: true`, all input is interactive. Use ordinary questions for grounded document QA and `exit` or `quit` to stop. The active feature branch additionally accepts `/related <topic>` for its related-problem baseline. With conversation mode disabled, `query` in `config.yml` is run once.

## Curated source library

- *Computer Vision: Algorithms and Applications* — computer vision methods and applications
- *Designing Data-Intensive Applications* — scalable and distributed data systems
- *Grokking the System Design Interview* — practical system-design case studies
- *LeetCode 4000 Problem Reference* — 4,000 coding-problem specifications and constraints
- *Probabilistic Machine Learning* — probabilistic modeling and inference
- *Speech and Language Processing* — NLP, speech, and language models

## Evaluation

The fixed benchmark in [`evaluation-data/rag_benchmark_v1.jsonl`](evaluation-data/rag_benchmark_v1.jsonl) contains 47 answerable questions and three controlled-unanswerable questions. It records reference answers, atomic facts, exact PDF evidence with physical page numbers, allowed sources, terminology variants, distractors, and audit metadata. Benchmark v1.2 pins the expanded LeetCode reference and reverifies its seven affected examples.

Run the full benchmark or a small execution check with:

```bash
python evaluate.py
python evaluate.py --limit 1
```

The evaluator imports the same `RAGPipeline` used by `main.py`. For answerable questions, evidence precision and recall compare the final reranked chunks supplied to Qwen with annotated evidence using normalized PDF word positions. The unanswerable outputs are retained for manual inspection.

These metrics evaluate retrieval and context coverage—not answer correctness, faithfulness, or semantic equivalence—and valid alternative evidence may not receive credit. The latest checked-in run and its exact configuration are in [`evaluation-results/summary.md`](evaluation-results/summary.md). Detailed records and per-question metrics are stored alongside it.

Additional benchmark documentation:

- [`evaluation-data/SCHEMA.md`](evaluation-data/SCHEMA.md) — record structure and field semantics
- [`evaluation-data/COVERAGE.md`](evaluation-data/COVERAGE.md) — source, category, and difficulty coverage
- [`evaluation-data/REVIEW.md`](evaluation-data/REVIEW.md) — human-readable question and evidence review
- [`evaluation-data/CHANGELOG.md`](evaluation-data/CHANGELOG.md) — dataset revisions and audits

## Repository layout

```text
.
├── main.py                 # RAG pipeline and conversation loop
├── evaluate.py             # Retrieval-focused benchmark runner
├── config.yml              # Models, prompts, indexing, retrieval, and ablations
├── requirements.txt
├── evaluation-data/        # Versioned benchmark and supporting documentation
├── evaluation-results/     # Latest checked-in reports
├── documents/              # Local source PDFs; git-ignored
└── index-data/              # Persisted local indexes; git-ignored
```

## Current limitations

- PDF extraction ignores figures, table structure, page layout, and scanned text without an OCR layer.
- `rank_bm25` scores every eligible chunk rather than using a scalable inverted index.
- Conversation state exists only for the current process and has no dedicated benchmark.
- There is no serving API or graphical interface; interaction is through the terminal.
- The related-problem baseline uses direct lexical/semantic retrieval and a generic cross-encoder, so it may miss indirect conceptual relationships.
- Recommendation quality is not yet measured by a dedicated benchmark.
