# Full title-first LeetCode benchmark comparison

All 40 frozen v2 questions were attempted independently: 36 ordinary requests and four explicit-naming controls. The current production workflow used Azure GPT-5.1, all 4,000 numbers/titles, a shortlist of up to 20 full statements, and up to three recommendations. Two isolated workers loaded existing indexes. Only the results directory was overridden in memory; production code, configuration, questions and labels were unchanged during execution.

| Metric | Previous retrieval (shortlist 30) | Title-first |
|---|---:|---:|
| Assessed precision | 35/35 (100.0%) | 46/46 (100.0%) |
| Hit rate | 18/36 (50.0%) | 24/30 (80.0%) |
| Annotated-target recall (micro) | 35/668 (5.2%) | 46/589 (7.8%) |
| Label coverage | 37/108 (34.3%) | 46/79 (58.2%) |
| Recommendations | 108 | 79 |
| Ordinary abstentions | 1/36 (2.8%) | 0/30 (0.0%) |
| Naming-control conformance | 3/4 (75.0%) | 4/4 (100.0%) |
| Execution failures | 0 | 6 |
| Mean question latency | 209.5 s | 43.6 s |
| LLM calls | 3225 | 159 |
| Recorded API tokens | 3785403 | 1980927 |

The previous run used a 400-token grounded-answer limit; this run used 1,200. The comparison therefore changes both selection workflow and answer budget. Dataset, reference and PDF hashes and all question texts match the saved previous run.

Assessed precision uses frozen direct, related and stretch labels; uncertain, unassessed and invalid mappings are excluded. The production model's own connection grade is not the evaluation label. Current reference labels: `{'direct_match': 10, 'stretch_connection': 15, 'related_practice': 21, 'unassessed': 32, 'unscored': 1}`. All-return usefulness bounds are 58.2%–100.0%. These are incomplete-label bounds, not confidence intervals.

Reported recall includes 35 previous and 29 current ordinary questions with valid mappings. On their common 29 eligible questions, annotated-target recall is 31/589 (5.3%) previous versus 46/589 (7.8%) current. The positive target set is incomplete, and a maximum of three returned problems per question limits its coverage.

## Execution diagnostics

- Paired ordinary-question changes: `{'gained_hit': 10, 'retained_hit': 14, 'lost_hit': 2, 'no_confirmed_hit_either_run': 4, 'execution_failure_in_either_run': 6}`.
- On the same 30 successfully completed ordinary questions: previous confirmed-hit rate 16/30 (53.3%); current 24/30 (80.0%).
- Confirmed hits per all 36 attempted ordinary questions: 24/36 (66.7%). Failed executions remain explicit failures, not abstentions.
- Six execution failures are listed below; they are excluded from completed-question metric denominators.
- Completed-output selection passes: 64; extra validation attempts: 4; application-level token-rate retries: 7. Failed phases may lack pass-level traces; their errors and total calls remain recorded separately.
- Mapping failures: 1. Execution failures are retained separately and are not abstentions.
- API finish reasons across recorded calls: `{'stop': 131, 'length': 17}`. These are aggregate counts across expansion, answering and selection.
- End-to-end elapsed time, including verification/initialization: 899.2 seconds.
- Per-question times include first-use loading, request serialization and retry delays; API usage is not an Azure bill.
- No additional evaluation LLM or semantic relabeling was used. All unseen identities are exported to pending review.

## Reliability failures

| Question ID | Failure |
|---|---|
| `lcrec-v2-005-descriptive` | Azure 429 token-rate limit during grounded-answer generation |
| `lcrec-v2-008-descriptive` | Azure 429 token-rate limit during grounded-answer generation |
| `lcrec-v2-010-short` | Azure 429 token-rate limit during grounded-answer generation |
| `lcrec-v2-012-descriptive` | Azure 429 token-rate limit during grounded-answer generation |
| `lcrec-v2-016-descriptive` | Duplicate title-shortlist IDs remained after one corrective retry |
| `lcrec-v2-018-short` | Duplicate title-shortlist IDs remained after one corrective retry |

One additional recommendation is mapping-unscored: question `lcrec-v2-018-descriptive`, problem **542**. Its technical quote came from **Computer Vision: Algorithms and Applications.pdf**, physical page 285, while the question allows only **Speech and Language Processing.pdf**. Its quote provenance does not satisfy that source restriction; it is excluded from precision, and the question is excluded from annotated-target recall.

Some technical answers still reach the larger answer ceiling; for example, `lcrec-v2-001-short` ends mid-sentence and has a recorded length-limit completion. Raising the budget to 1,200 did not eliminate every truncated answer. Original technical passages were also supplied to both selectors.

## Per-question comparison

D=direct, R=related, S=stretch, X=unrelated, ?=uncertain, U=unassessed, !=mapping-unscored.

| Question | Previous recommendations | Title-first recommendations | Previous / current hit | Previous / current seconds |
|---|---|---|---|---:|
| `lcrec-v2-001-short` | Abstain | 2642 (D), 1631 (S), 2290 (R) | No confirmed hit / Yes | 6.5 / 58.5 |
| `lcrec-v2-001-descriptive` | 1786 (R), 2699 (R), 2642 (D) | 64 (D), 1091 (D), 1631 (S) | Yes / Yes | 237.8 / 53.2 |
| `lcrec-v2-002-short` | 1489 (U), 3553 (U), 3613 (R) | 2290 (U), 130 (U), 542 (U) | Yes / No confirmed hit | 250.2 / 78.4 |
| `lcrec-v2-002-descriptive` | 3419 (?), 2203 (U), 3650 (U) | 2290 (U), 1631 (U), 934 (U) | No confirmed hit / No confirmed hit | 217.5 / 25.1 |
| `lcrec-v2-003-short` | 1959 (U), 480 (U), 3645 (U) | 661 (U), 289 (U) | No confirmed hit / No confirmed hit | 198.7 / 52.8 |
| `lcrec-v2-003-descriptive` | 2587 (U), 1331 (U), 3321 (U) | 1093 (R), 571 (U), 1480 (U) | No confirmed hit / Yes | 272.4 / 50.5 |
| `lcrec-v2-004-short` | 3663 (U), 3852 (U), 3003 (U) | 3167 (U), 3163 (U), 451 (U) | No confirmed hit / No confirmed hit | 243.1 / 37.7 |
| `lcrec-v2-004-descriptive` | 2671 (U), 49 (U), 988 (U) | 2268 (D), 820 (S), 451 (U) | No confirmed hit / Yes | 256.5 / 26.1 |
| `lcrec-v2-005-short` | 1947 (D), 2323 (U), 3276 (R) | 1947 (D) | Yes / Yes | 240.1 / 39.9 |
| `lcrec-v2-005-descriptive` | 3476 (U), 1947 (D), 1066 (D) | Execution failed | Yes / Failed | 224.4 / 16.9 |
| `lcrec-v2-006-short` | 528 (D), 497 (R), 2587 (U) | 528 (D), 497 (R), 470 (R) | Yes / Yes | 267.1 / 30.0 |
| `lcrec-v2-006-descriptive` | 528 (D), 2599 (U), 382 (R) | 528 (D), 497 (R), 470 (R) | Yes / Yes | 231.7 / 74.7 |
| `lcrec-v2-007-short` | 1606 (R), 173 (U), 641 (S) | 1606 (R) | Yes / Yes | 223.1 / 55.6 |
| `lcrec-v2-007-descriptive` | 61 (U), 1882 (U), 1656 (U) | 1606 (R), 622 (S), 1823 (S) | No confirmed hit / Yes | 207.4 / 25.3 |
| `lcrec-v2-008-short` | 1157 (U), 308 (U), 3195 (U) | 427 (D), 558 (R), 1274 (U) | No confirmed hit / Yes | 246.0 / 32.8 |
| `lcrec-v2-008-descriptive` | LeetCode_4000_Problem_Reference.pdf::page=1791::problem=3578 (!), LeetCode_4000_Problem_Reference.pdf::page=1502::problem=3003 (!), LeetCode_4000_Problem_Reference.pdf::page=1966::problem=3929 (!) | Execution failed | No confirmed hit / Failed | 256.3 / 8.3 |
| `lcrec-v2-009-short` | 271 (S), 717 (R), 1256 (S) | 393 (R), 271 (S), 1256 (S) | Yes / Yes | 318.2 / 26.5 |
| `lcrec-v2-009-descriptive` | 393 (R), 3023 (U), 271 (S) | 393 (R), 190 (U), 2433 (U) | Yes / Yes | 266.4 / 48.1 |
| `lcrec-v2-010-short` | 3058 (U), 1158 (U), 1892 (U) | Execution failed | No confirmed hit / Failed | 185.6 / 17.1 |
| `lcrec-v2-010-descriptive` | 3497 (U), 1892 (U), 3808 (U) | 349 (S), 350 (S), 2956 (S) | No confirmed hit / Yes | 198.0 / 28.0 |
| `lcrec-v2-011-short` | 1817 (U), 1113 (U), 2329 (U) | 811 (R), 347 (U), 692 (U) | No confirmed hit / Yes | 226.3 / 82.6 |
| `lcrec-v2-011-descriptive` | 3214 (U), 1336 (U), 3230 (U) | 1418 (U), 811 (R), 2570 (U) | No confirmed hit / Yes | 179.9 / 77.4 |
| `lcrec-v2-012-short` | 3204 (R), 2275 (R), 2980 (S) | 898 (S), 2411 (S), 2166 (U) | Yes / Yes | 232.4 / 23.3 |
| `lcrec-v2-012-descriptive` | 2461 (U), 2901 (U), 3117 (S) | Execution failed | Yes / Failed | 232.8 / 5.6 |
| `lcrec-v2-013-short` | 1297 (U), 2609 (U), 1593 (U) | 87 (R), 139 (U), 140 (U) | No confirmed hit / Yes | 262.8 / 27.9 |
| `lcrec-v2-013-descriptive` | 2953 (U), 3579 (U), 1520 (U) | 241 (R), 1547 (U), 132 (U) | No confirmed hit / Yes | 266.6 / 77.6 |
| `lcrec-v2-014-short` | 3600 (S), 1489 (R), 2378 (U) | 1489 (R), 1135 (R), 1584 (R) | Yes / Yes | 212.9 / 63.3 |
| `lcrec-v2-014-descriptive` | 2378 (U), 685 (U), 1489 (R) | 1135 (R), 1584 (R), 261 (U) | Yes / Yes | 242.1 / 23.3 |
| `lcrec-v2-015-short` | 1441 (S), 150 (R), 241 (U) | 946 (S) | Yes / Yes | 241.7 / 55.7 |
| `lcrec-v2-015-descriptive` | 1441 (S), 150 (R), 1381 (S) | 1441 (S), 946 (S), 394 (R) | Yes / Yes | 227.9 / 65.6 |
| `lcrec-v2-016-short` | 1348 (U), 147 (U), 1656 (U) | 1902 (U) | No confirmed hit / No confirmed hit | 204.3 / 63.9 |
| `lcrec-v2-016-descriptive` | 708 (U), 2811 (U), 88 (U) | Execution failed | No confirmed hit / Failed | 204.8 / 47.6 |
| `lcrec-v2-017-short` | 1188 (D), 1116 (U), 1226 (U) | 1188 (D) | Yes / Yes | 234.0 / 53.8 |
| `lcrec-v2-017-descriptive` | 622 (R), 641 (R), 1882 (U) | 1188 (D), 1195 (U), 1115 (U) | Yes / Yes | 219.7 / 51.5 |
| `lcrec-v2-018-short` | 3923 (U), 1828 (U), 1515 (?) | Execution failed | No confirmed hit / Failed | 209.9 / 25.0 |
| `lcrec-v2-018-descriptive` | 3030 (S), 3923 (U), 26 (U) | 973 (U), LeetCode_4000_Problem_Reference.pdf::page=271::problem=542 (!), 239 (U) | Yes / No confirmed hit | 211.8 / 92.4 |
| `lcrec-v2-019-short` | Abstain | Abstain | Control pass / Control pass | 4.0 / 75.9 |
| `lcrec-v2-019-descriptive` | Abstain | Abstain | Control pass / Control pass | 5.5 / 12.1 |
| `lcrec-v2-020-short` | Abstain | Abstain | Control pass / Control pass | 2.6 / 7.2 |
| `lcrec-v2-020-descriptive` | 2157 (U), 30 (U), 1203 (U) | Abstain | Control fail / Control pass | 209.6 / 28.5 |

These results describe the fixed development benchmark. Incomplete relevance labels, narrow title hints, technical-retrieval failures and model-judged connections remain limitations. Literal quote/identity validation establishes provenance, not semantic correctness.

[Full report](summary.md) · [Structured details](details.json) · [Per-question CSV](per_question.csv) · [Unassessed pairs](pending_review.jsonl)
