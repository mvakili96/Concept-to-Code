# Source-restriction fix: updated collective results

**Only two questions were rerun; the other 38 result records are unchanged.** All 40 evaluations now complete, and all selected recommendation evidence satisfies its question's source restriction. The previous collective report is preserved.

| Metric | Before source fix | Updated collective results |
|---|---:|---:|
| Assessed precision | 55/55 (100.0%) | 57/57 (100.0%) |
| Confirmed ordinary-question hit rate | 28/36 (77.8%) | 29/36 (80.6%) |
| Annotated-target recall (micro) | 55/660 (8.3%) | 57/670 (8.5%) |
| Label coverage | 55/96 (57.3%) | 57/96 (59.4%) |
| Source/mapping-unscored recommendations | 4 | 0 |
| Execution failures | 0 | 0 |
| Naming controls passed | 4/4 | 4/4 |

The prior recall excluded the two questions with invalid source mappings. Updated recall includes all 36 ordinary questions and their 670 annotated targets. These targets are incomplete and this is not exhaustive semantic recall. Assessed precision excludes unassessed recommendations; there are 39 such returns in the updated results, not automatically correct or incorrect.

## Two new evaluations

| Question | Requested and verified technical PDF | Recommendations (frozen reference labels) |
|---|---|---|
| `lcrec-v2-008-descriptive` | Grokking-the-system-design-interview-free.pdf | 427 (direct_match), 558 (related_practice), 1274 (unassessed) |
| `lcrec-v2-018-descriptive` | Speech and Language Processing.pdf | 973 (unassessed), 658 (unassessed), 295 (unassessed) |

The quadtree question now uses Grokking evidence for problems 427, 558 and 1274. The first two carry positive reference labels; the third is unassessed. All three cluster-center recommendations also have verified evidence from the requested Speech and Language Processing PDF, but their problem/topic pairs are unassessed in the frozen benchmark.

The source parser now accepts exact quoted PDF filenames anywhere in a prompt, retaining exact spelling, case and extension checks. The benchmark questions, labels, model settings, answer budgets and indexes were unchanged. One worker and a 65-second gap between questions reduced quota pressure. One verification response required its existing corrective retry; no quota errors occurred.

## Provenance and recorded usage

This is a composite of 33 retained initial-run records, five retained deduplication-recovery records, and two new source-fixed evaluations. Each record keeps its source run ID. The configuration and timing header in summary.md describes the newest two-question segment; aggregate latency is not a fresh homogeneous full-run measurement.

- New two-question inference: `{'llm_calls': 9, 'token_usage': {'prompt_tokens': 98858, 'completion_tokens': 4507, 'total_tokens': 103365}}`.
- Selected 40 result records: `{'llm_calls': 167, 'token_usage': {'prompt_tokens': 2039321, 'completion_tokens': 66851, 'total_tokens': 2106172}}`.
- Cumulative original evaluation and all targeted reruns, including superseded attempts: `{'llm_calls': 192, 'token_usage': {'prompt_tokens': 2307578, 'completion_tokens': 74020, 'total_tokens': 2381598}}`.

No additional evaluation LLM or label edits were used. Recorded usage may omit SDK retries or failed-request usage and is not an Azure bill.

[Updated summary](summary.md) · [Details](details.json) · [Two-question report](rerun-two/summary.md) · [Provenance](source_fix_provenance.json)
