# Document QA Evaluation Summary

Evidence text precision and recall are deterministic normalized word-position overlap against annotated passages. This project evaluates RAG retrieval and reranking rather than the quality of the final language model, so generated answers are not assigned correctness or faithfulness scores. Dataset eligibility is based on automatic source verification, not human review.

- Run timestamp: 2026-10-26T21:03:31.176546+00:00
- Coverage: full verified dataset
- Evaluated questions: 50
- Eligible dataset questions: 50
- Excluded questions: 0 (0 quarantined, 0 unresolved)
- Answer model: `gpt-5.1`
- LLM provider: `azure_openai`
- Dataset: `evaluation-data/document-qa/rag_benchmark_v1.jsonl`
- Config: `config.yml`

| Metric | Average | Scored denominator | N/A | Failed/unscored |
|---|---:|---:|---:|---:|
| Evidence text precision | 0.1876 | 47 | 3 | 0 |
| Evidence text recall | 0.7321 | 47 | 3 | 0 |

Averages include scored examples only. N/A and failed/unscored judgments are excluded from each denominator.
Evidence text overlap measures coverage of the specifically annotated passages, not semantic correctness, and may miss valid alternative evidence.

## Pipeline configuration

- Azure settings (no API key): `{'base_url': 'https://concept-to-code-resource.openai.azure.com/openai/v1/', 'reasoning_effort': 'none', 'timeout_seconds': 60, 'max_retries': 1}`
- Indexing mode: `load`
- Persisted index directory: `index-data`
- Dense retrieval enabled: `True`
- BM25 retrieval enabled: `True`
- Query expansion enabled: `True`
- Model-text normalization: `{'enabled': True, 'version': 1}`
- Focused dense/reranking query: `True` (applies only when BM25 and query expansion are enabled)
- Query-expansion limits (key terms / acronyms / variations): 3 / 4 / 2
- Chunk size/overlap: 900 / 200 characters
- Dense FAISS index: `flat`
- Dense top-k / BM25 top-k: 50 / 50
- Final reranked top-k: 4
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- Reranker model: `cross-encoder/ms-marco-MiniLM-L6-v2`
- Source name included in reranker input: `True`

## Generated answers for unanswerable questions

These outputs are included for manual inspection of whether the answer model recognized that the retrieved context was insufficient; they are not scored.

### `ragbench-v1-048`

Question: According to "Computer Vision: Algorithms and Applications.pdf", which word-level edit operations underlie word error rate, and what range exception is noted because insertions are included?

Generated answer:

> The provided document context does not contain enough information to answer this question.

### `ragbench-v1-049`

Question: According to "Designing Data-Intensive Applications.pdf", how does byte-pair encoding training grow its token vocabulary?

Generated answer:

> The provided document context does not contain enough information to determine how byte-pair encoding training grows its token vocabulary. The excerpts from *Designing Data-Intensive Applications.pdf* (pages 135, 138, 141, 144) discuss binary encoding formats, Thrift’s CompactProtocol, variable-length integers, and JSON binary encodings, but do not mention byte-pair encoding or its training process.
>
> Therefore, this information is not available in the given sources and pages:
>
> - SOURCE: Designing Data-Intensive Applications.pdf, PAGE: 135  
> - SOURCE: Designing Data-Intensive Applications.pdf, PAGE: 138  
> - SOURCE: Designing Data-Intensive Applications.pdf, PAGE: 141  
> - SOURCE: Designing Data-Intensive Applications.pdf, PAGE: 144

### `ragbench-v1-050`

Question: According to "Grokking-the-system-design-interview-free.pdf", how do forward and reverse KL differ in mode-covering versus mode-seeking behavior?

Generated answer:

> The provided document context does not contain enough information to determine how forward and reverse KL differ in mode-covering versus mode-seeking behavior. None of the cited pages (SOURCE: Grokking-the-system-design-interview-free.pdf, PAGES: 99, 145, 184, 193) discuss KL divergence or mode-covering/mode-seeking.
