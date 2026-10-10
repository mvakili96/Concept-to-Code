# Exploring RAG

A compact, local pipeline for progressively exploring production RAG concepts over PDF documents.

## Pipeline at a glance

| Component | Implementation |
|---|---|
| **PDF ingestion** | `pypdf` |
| **Chunking** | LangChain recursive text splitting |
| **Dense retrieval** | MiniLM embeddings + `FAISS` IndexFlat (exact k-NN) or HNSW (ANN) |
| **Sparse retrieval** | `BM25` with optional Qwen-based query expansion |
| **Candidate fusion** | Chunk-ID deduplication |
| **Reranking** | MiniLM cross-encoder |
| **Generation** | `Qwen2.5-7B-Instruct` with source and page citations |
| **Conversation** | Qwen follow-up rewriting, in-memory history, and active-source state |
| **Related-problem workflow** | Technical evidence → Qwen pattern extraction → LeetCode retrieval through `/related` |
| **Persistence** | Reusable corpus, BM25, IndexFlat, and HNSW artifacts |
| **Ablations** | Independent dense retrieval, BM25, and query-expansion toggles |
| **Evaluation** | 50-question source-grounded benchmark with deterministic evidence-overlap metrics |

IndexFlat compares the query with every stored vector, while HNSW navigates a graph and trades a small chance of missing the exact nearest chunks for faster search on large indexes. Both return the requested top-k results. An exactly named PDF restricts retrieval to that source; otherwise, the entire corpus is searched.

## Running

Retrieval sources belong in `documents/`, which is git-ignored. Install the dependencies listed in [requirements.txt](requirements.txt) with `pip install -r requirements.txt`, then configure [config.yml](config.yml) and run `python main.py`. Models, prompts, the query, chunking, indexing, retrieval, and ablation settings are defined in that configuration file.

Use indexing mode `build` once to parse and chunk the complete corpus, build BM25 plus both Flat and HNSW indexes, persist them under the git-ignored `index-data/`, and answer the configured query. Then switch to `load` to skip ingestion and index construction. `dense_index_type` selects the persisted Flat or HNSW index without rebuilding.

`use_dense_retrieval`, `use_bm25_retrieval`, and `use_query_expansion` support retrieval ablations without rebuilding. At least one retriever must remain enabled, and query expansion runs only when BM25 is enabled.

With `conversation.enabled`, every turn—including the first—is entered interactively in the terminal; the configured query is used only in single-turn mode. Later turns are rewritten into standalone retrieval queries using recent user and assistant messages. An explicitly named source is inherited only for a follow-up and cleared for a new topic. History resolves references but is not treated as document evidence; session state lasts only for the current process.

Use `/related <technical topic or request>` in conversation mode to run the separate related-problem workflow. It first retrieves and reranks technical evidence from an exactly named technical PDF, or from every non-LeetCode source when none is named. Qwen assesses evidence sufficiency and extracts literal source terms, inferred coding patterns, topic connections, quotes, and coding tasks. Python checks terms and short quotes after Unicode, whitespace, and line-break-hyphen normalization, retains valid items across one targeted retry, and builds the LeetCode search query only from accepted coding tasks. Insufficient evidence or no surviving patterns falls back to the original request. The terminal shows accepted patterns, rejected-item diagnostics, and the search query; Qwen receives both contexts for recommendations. Topic connections are model inferences, not guaranteed relevance checks. The workflow does not yet use or update conversation memory.

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

This repository evaluates retrieval and reranking rather than final-answer quality. Generated answers are retained, and answers to the three unanswerable questions are shown for manual inspection. Each run records the indexing and ablation configuration and replaces `summary.md`, `per_question.csv`, and `details.json` in `evaluation-results/`.

## Current limitations

- Figures, table structure, page layout, and scanned text are not parsed.
- `rank_bm25` scores every chunk rather than using a scalable inverted index.
- Conversation sessions are not persisted, and there is no conversational benchmark or serving API yet.
- Pattern quotes are checked for text occurrence, but conceptual relationships and recommendations still need a dedicated relevance benchmark.
