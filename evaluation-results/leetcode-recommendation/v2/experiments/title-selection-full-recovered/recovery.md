# Recovered collective LeetCode results

**Offline metric update:** Capped Recall@3 averages each eligible question's target hits divided by `min(3, positive target count)`. Match, Relevant, and Stretch count when in the annotated target set. Saved predictions and original inference metadata are unchanged. The original recall discussion below refers to full annotated-target recall, now a secondary diagnostic. Eligible question counts: 34.

**34 saved successful evaluations were reused unchanged; only the six previously failed questions were rerun.** The original full report and its failures remain intact. This report combines two code/execution snapshots, rather than claiming a fresh homogeneous run on all 40 questions.

| Metric | Collective result |
|---|---:|
| Completed questions | 40/40 (100.0%) |
| Assessed precision | 55/55 (100.0%) |
| Confirmed hit rate, all ordinary attempts | 28/36 (77.8%) |
| Capped recall@3 (macro) | 54.9% |
| Full annotated-target recall (secondary) (micro) | 55/660 (8.3%) |
| Label coverage | 55/96 (57.3%) |
| Naming controls conforming | 4/4 (100.0%) |
| Execution failures remaining | 0 |

The initial full run had confirmed useful outputs for 24/36 ordinary attempts (66.7%); the collective report has 28/36 (77.8%). The earlier 80% hit rate excluded its six failed executions. Both figures here use all 36 ordinary requests.

Reference label counts: `{'direct_match': 12, 'stretch_connection': 18, 'related_practice': 25, 'unassessed': 37, 'unscored': 4}`. Unassessed and mapping-unscored returns are excluded from assessed precision. Frozen labels remain incomplete, and no semantic evaluation LLM or new relevance labels were introduced.

## Six recovered executions

D=direct, R=related, S=stretch, U=unassessed, !=mapping-unscored.

| Question | Previous failure | Retry status | New recommendations and frozen labels | Seconds | Calls |
|---|---|---|---|---:|---:|
| `lcrec-v2-005-descriptive` | Azure token-rate limit | completed | 1947 (D), 1057 (R), 2410 (D) | 27.3 | 4 |
| `lcrec-v2-008-descriptive` | Azure token-rate limit | completed | 427 (!), 558 (!), 1274 (!) | 23.7 | 4 |
| `lcrec-v2-010-short` | Azure token-rate limit | completed | 350 (S), 706 (U), 349 (S) | 11.9 | 4 |
| `lcrec-v2-012-descriptive` | Azure token-rate limit | completed | 3204 (R), 2275 (R), 201 (S) | 19.1 | 4 |
| `lcrec-v2-016-descriptive` | Duplicate title-shortlist IDs after retry | completed | 776 (R), 108 (U), 352 (U) | 21.8 | 4 |
| `lcrec-v2-018-short` | Duplicate title-shortlist IDs after retry | completed | 346 (U), 973 (U) | 14.4 | 4 |

## Source restrictions and execution provenance

Mapping/source-restriction failures retained as unscored: `[{'question_id': 'lcrec-v2-008-descriptive', 'problem_id': 'LeetCode_4000_Problem_Reference.pdf::page=214::problem=427', 'error': "Technical evidence violates the question's source restriction."}, {'question_id': 'lcrec-v2-008-descriptive', 'problem_id': 'LeetCode_4000_Problem_Reference.pdf::page=279::problem=558', 'error': "Technical evidence violates the question's source restriction."}, {'question_id': 'lcrec-v2-008-descriptive', 'problem_id': 'LeetCode_4000_Problem_Reference.pdf::page=637::problem=1274', 'error': "Technical evidence violates the question's source restriction."}, {'question_id': 'lcrec-v2-018-descriptive', 'problem_id': 'LeetCode_4000_Problem_Reference.pdf::page=271::problem=542', 'error': "Technical evidence violates the question's source restriction."}]`.

The reused segment used the pre-deduplication code with two workers. The six retries used the order-preserving ID-deduplication fix, one worker, and a 65-second cooldown between questions. Models, prompts, source hashes, reference labels, retrieval/index settings and answer budgets were unchanged. Original record run IDs are retained; both code hashes and the per-segment question IDs are recorded in details.json and recovery_provenance.json.

## Recorded usage

- New six-question inference only: `{'llm_calls': 24, 'token_usage': {'prompt_tokens': 286526, 'completion_tokens': 10780, 'total_tokens': 297306}}`.
- Selected 40 question records: `{'llm_calls': 167, 'token_usage': {'prompt_tokens': 2037807, 'completion_tokens': 66611, 'total_tokens': 2104418}}`.
- Cumulative original run plus the six retries, including superseded failed attempts: `{'llm_calls': 183, 'token_usage': {'prompt_tokens': 2208720, 'completion_tokens': 69513, 'total_tokens': 2278233}}`.

Usage is recorded telemetry rather than a billing estimate. Mixed per-question latency excludes cooldowns and is not a controlled full-run timing result. No model calls regenerated the 34 retained answers or recommendations.

[Collective summary](summary.md) · [Details](details.json) · [Six-question retry report](retry-six/summary.md) · [Provenance](recovery_provenance.json)
