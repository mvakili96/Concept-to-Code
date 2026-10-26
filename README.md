# Exploring RAG

A compact, local pipeline for progressively exploring production RAG concepts over PDF documents.

## Pipeline at a glance

| Component | Implementation |
|---|---|
| **PDF ingestion** | `pypdf` |
| **Chunking** | LangChain recursive text splitting |
| **Text normalization** | Model-facing Unicode ligature, line-break-hyphen, and whitespace normalization; raw citation offsets preserved |
| **Dense retrieval** | MiniLM embeddings + `FAISS` IndexFlat (exact k-NN) or HNSW (ANN) |
| **Sparse retrieval** | `BM25` with optional Qwen-based query expansion |
| **Candidate fusion** | Chunk-ID deduplication |
| **Reranking** | MiniLM cross-encoder |
| **Generation** | `Qwen2.5-7B-Instruct` with source and page citations |
| **Conversation** | Qwen follow-up rewriting, in-memory history, and active-source state |
| **Related-problem workflow** | Technical evidence → coding patterns → multi-query LeetCode retrieval → conceptual reranking through `/related` |
| **Persistence** | Reusable corpus, BM25, IndexFlat, and HNSW artifacts |
| **Ablations** | Independent dense retrieval, BM25, and query-expansion toggles |
| **Evaluation** | 50-question source-grounded benchmark with deterministic evidence-overlap metrics |

IndexFlat compares the query with every stored vector, while HNSW navigates a graph and trades a small chance of missing the exact nearest chunks for faster search on large indexes. Both return the requested top-k results. An exactly named PDF restricts retrieval to that source; otherwise, the entire corpus is searched.

## Running

Retrieval sources belong in `documents/`, which is git-ignored. Install the dependencies listed in [requirements.txt](requirements.txt) with `pip install -r requirements.txt`, then configure [config.yml](config.yml) and run `python main.py`. Models, prompts, the query, chunking, indexing, retrieval, and ablation settings are defined in that configuration file.

Use indexing mode `build` once to parse and chunk the complete corpus, build BM25 plus both Flat and HNSW indexes, persist them under the git-ignored `index-data/`, and answer the configured query. Then switch to `load` to skip ingestion and index construction. `dense_index_type` selects the persisted Flat or HNSW index without rebuilding.

`use_dense_retrieval`, `use_bm25_retrieval`, and `use_query_expansion` support retrieval ablations without rebuilding. At least one retriever must remain enabled, and query expansion runs only when BM25 is enabled.

`text_normalization.enabled` normalizes embedding, BM25, reranking, and context inputs without changing stored PDF text, chunks, IDs, or citation offsets; changing it requires an index rebuild. The same query-expansion pass optionally supplies a focused dense/reranking query (`query_expansion.use_focused_query`), while BM25 uses the original question plus conservative wording variations. Source restrictions and the answering question remain based on the original query. Focused queries are available only when BM25 and query expansion are enabled; disabling the option retains the original dense/reranking query. Candidate limits default to 50 per retriever before the final four reranked chunks; expansion and top-k settings can change without rebuilding.

`reranking.include_source_name` supplies the existing source label alongside each chunk's normalized body, retaining document/domain context for chunks without headings. This query-time setting does not require rebuilding indexes.

With `conversation.enabled`, every turn—including the first—is entered interactively in the terminal; the configured query is used only in single-turn mode. Later turns are rewritten into standalone retrieval queries using recent user and assistant messages. An explicitly named source is inherited only for a follow-up and cleared for a new topic. History resolves references but is not treated as document evidence; session state lasts only for the current process.

Use `/related <technical topic or request>` in conversation mode to run the separate related-problem workflow. It first retrieves and reranks technical evidence from an exactly named technical PDF, or from every non-LeetCode source when none is named. Qwen assesses evidence sufficiency and extracts literal source terms, inferred coding patterns, topic connections, quotes, and coding tasks. Each pattern selects a Python-assigned passage ID; quotes must match that passage after Unicode, whitespace, and line-break-hyphen normalization. Invalid quotes get one focused retry using only the selected passage, selecting literal excerpt IDs when available so Python copies the quote; other extraction errors retain one targeted retry. A separate Qwen pass translates accepted patterns into concise coding-problem queries. Each query independently searches the LeetCode PDF using enabled dense/BM25 components; candidates are deduplicated by chunk ID before the existing reranker scores them against the combined task queries. Per-query retrieval limits remain in `retrieval`; query-construction settings are in `related_problem.candidate_retrieval`. Invalid query plans reuse the previous coding-task bridge; insufficient technical evidence falls back to the original request. Returned results retain the query plan, candidate counts, chunk IDs, and retrieval provenance without printing diagnostic JSON in the terminal. Qwen compares technical passages with individual problem statements. Topic connections are model inferences, not guaranteed relevance checks. The workflow does not yet use or update conversation memory.

For `/related` only, `related_problem.conceptual_reranking` configures a cross-encoder chunk shortlist. Numbered headings identify problems whose bodies overlap those chunks; Python fetches each complete statement from saved PDF text, bounded by its heading and the next heading/footer, before judging. Original parent chunk IDs and `retrieved_problem_spans` remain separate from full-body `problem_spans`; `problem_expanded` records added coverage. Qwen first extracts each problem's explicit operations without seeing the question or technical topic, then compares one frozen operation with one source-backed technical pattern. Useful suggestions are labeled **direct match**, **related practice**, or **stretch connection**; partial computational connections are welcome, but shared vocabulary alone is not. Python validates the evidence selections; user constraints are supplied only to the comparison call. The independent check sets the final level and explains what transfers and what does not. The existing cross-encoder rescores complete accepted statements against the coding-search queries; closer practice levels rank first, with cross-encoder scores ordering problems within each level, before applying `reranking.final_top_k`. Original chunk scores and new problem scores are retained separately. Python then selects the top approved problems in that order, deduplicated and capped by `related_problem.recommendation_validation.max_recommendations` (default three). No final LLM selection call is made: numbers, titles, and difficulty come directly from verified source headings, while explanations, differences, quotes, and source/page citations come from the existing checked assessments. No passing candidates means abstention, not proof that no related problem exists in the corpus. Missing/ambiguous boundaries or failed source mappings are flagged, not guessed. `recommendation_validation` records the deterministic method, selected IDs, and any rejected records; its LLM attempts list is empty. No catalog or index rebuild is needed. Ordinary QA and benchmark evaluation are unchanged.

Judging is anchored to the accepted patterns actually used for search: Python retains their original technical quotes and source links, with no separate LLM-selected relationship. Each supported match names one existing pattern index, and the independent check uses that same pattern and its original passage. The first call sees only the statement and numbered problem spans, extracting up to `related_problem.conceptual_reranking.max_problem_operations` atomic operations (default three). Python assigns operation IDs; the second call selects one existing operation ID and one technical pattern, then explains an evidence-linked component on each side and its limitations. It cannot rewrite the coding operation or replace its selected quote. They select numbered prose spans instead of reproducing quotes; Python copies the original text and records body-relative character offsets. Problem constraint lines are not selectable mechanism evidence. The independent check separately grounds each operation in its own source, then judges shared-component support: different operations can both be grounded without being equivalent or even related. All three support decisions must pass for a recommendation. Empty extractions abstain; invalid extraction or comparison responses are individually unscored after their bounded retry. More candidates can now reach the comparison call, increasing latency; no additional cache or index is introduced. The earlier combined operation-support field is retained only as a derived diagnostic value. Invalid responses retain one corrective retry. Mechanism-level related practice can differ in implementation or objective; those differences are reported explicitly. Span selection verifies provenance, while semantic support remains a model judgment. The configurable cross-encoder shortlist now admits 20 chunks before individual-problem judging; final context remains capped at four passing problems. This query-time change needs no index rebuild and increases judging cost, not the final context limit.

Overlong `/related` coding tasks get one focused repair per source-linked pattern. Only the task sentence can change; the existing pattern, checked quote, and Python-owned citation remain fixed. Failed repairs retain the existing extraction retry/fallback. Retry prompts and token limits are in `related_problem.pattern_extraction`; returned `coding_task_repairs` records retain the original task, response, length, and outcome for diagnostics.

## Retrieval Sources

- *Computer Vision: Algorithms and Applications* — computer vision methods and applications.
- *Designing Data-Intensive Applications* — scalable and distributed data systems.
- *Grokking the System Design Interview* — practical system-design case studies.
- *LeetCode 4000 Problem Reference* — 4,000 coding-problem specifications and constraints.
- *Probabilistic Machine Learning* — advanced probabilistic modeling and inference.
- *Speech and Language Processing* — NLP, speech, and language models.

## Evaluation Dataset

`evaluation-data/rag_benchmark_v1.jsonl` is a fixed, source-grounded single-turn benchmark of 50 answerable and controlled-unanswerable questions. It includes reference answers, atomic facts, exact PDF evidence with physical page numbers, source restrictions, terminology variants, and distractors. Benchmark v1.2 pins the expanded LeetCode reference and re-audits its seven examples. The dataset exists to compare retrieval, query-expansion, reranking, and context-coverage changes consistently across experiments.

Run the complete automated evaluation with `python evaluate.py`, or use `python evaluate.py --limit 1` for a small execution check. The evaluator imports the same `RAGPipeline` used by `main.py`. Evidence text precision and recall compare only the final reranked chunks supplied to the answering LLM against the annotated passages using normalized PDF word positions. They do not measure semantic correctness and can miss valid alternative evidence.

This repository evaluates retrieval and reranking rather than final-answer quality. Generated answers are retained, and answers to the three unanswerable questions are shown for manual inspection. Each run records indexing, normalization, expansion/focused-query, candidate-limit, and ablation settings and replaces `summary.md`, `per_question.csv`, and `details.json` in `evaluation-results/`. Per-question details retain the focused retrieval query and BM25 query.

## Current limitations

- Figures, table structure, page layout, and scanned text are not parsed.
- `rank_bm25` scores every chunk rather than using a scalable inverted index.
- Qwen query rewrites and wording variations can still lose meaning or drift; numeric/primary-term checks are safeguards, not semantic guarantees.
- Conversation sessions are not persisted, and there is no conversational benchmark or serving API yet.
- Related-problem judgments and explanations remain model inferences, not guaranteed semantic validation. Identity parsing depends on the PDF heading/page-range format, and a dedicated relevance benchmark is still missing.
