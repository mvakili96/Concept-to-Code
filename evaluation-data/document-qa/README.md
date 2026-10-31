# Document-QA benchmark

This fixed benchmark contains **50 questions: 47 answerable and three controlled unanswerable questions**. It evaluates retrieval and reranking through the final context supplied to the answering LLM.

Each sample includes a question, allowed PDF sources, answerability, a reference answer, atomic required facts, exact supporting passages and fact links, evidence groups, optional terminology variants and distractors, and source-audit metadata. Evidence uses one-based physical PDF pages rather than printed book labels and is independent of retrieval chunk IDs.

- [`rag_benchmark_v1.jsonl`](rag_benchmark_v1.jsonl): one record per stable question ID.
- [`corpus_manifest_v1.json`](corpus_manifest_v1.json): original PDF hashes and extraction/page conventions.
- [REVIEW.md](REVIEW.md): questions, answers, facts, quotes, and page references together.
- [SCHEMA.md](SCHEMA.md), [COVERAGE.md](COVERAGE.md), and [CHANGELOG.md](CHANGELOG.md): field definitions, coverage, and changes.

The current benchmark is version `1.2.0` with schema `1.1.0`, despite the historical `v1` filename. Review status records automated source auditing, not human approval or guaranteed correctness.

Run `python evaluate_document_qa.py` from the repository root. Add `--limit 1` to evaluate the first question only. The scorer reports evidence text precision and recall, not generated-answer correctness or semantic fact coverage.

[Benchmark overview and sample examples](../README.md) · [Exact metric calculations](../METRICS.md#document-qa-evidence-text-precision-and-recall) · [Saved report](../../evaluation-results/document-qa/summary.md)
