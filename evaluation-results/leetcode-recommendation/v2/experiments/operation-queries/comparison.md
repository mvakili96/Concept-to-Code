# V2 operation-based query evaluation

Status: the operation-query implementation was reverted after this evaluation. The active pipeline uses the previous pattern-based workflow with shortlist 30, matching the [previous report](../shortlist-30/summary.md). These results and their frozen settings remain as experiment history.

## Conclusion

This run **does not demonstrate an improvement on the frozen benchmark labels**. Confirmed ordinary-question hit rate drops from 50.0% to 41.7%, annotated-target recall from 5.2% to 3.7%, and label coverage from 34.3% to 22.5%. Assessed precision stays at 100%, but its scored denominator shrinks from 35 to 25 recommendations; it is not overall accuracy. Most new outputs remain unassessed.

Both runs use shortlist **30**, the same 40 v2 questions, 360 frozen pair annotations, original PDFs/index artifacts, Azure deployment and two-worker execution, scoring, dense/BM25 candidate limits, four final context problems and a maximum of three recommendations. The new run evaluates the operation-based extraction/query feature, including its source mechanism representation, operation IDs and duplicate handling. No labels were revised after predictions.

- Previous run: `229b9e1c80d54e398b63d8f4d81c08f2`; [previous report](../shortlist-30/summary.md).
- Operation-query run: `04be2244fa78490cad5e32cd0cb114cc`; [new report](summary.md).

## Metrics

| Metric | Previous, shortlist 30 | Operation queries, shortlist 30 |
|---|---:|---:|
| Assessed precision | 35/35 (100.0%) | 25/25 (100.0%) |
| Confirmed hit rate | 18/36 (50.0%) | 15/36 (41.7%) |
| Hit-rate upper bound | 35/36 (97.2%) | 36/36 (100.0%) |
| Annotated-target recall (micro) | 35/668 (5.2%) | 25/668 (3.7%) |
| Label coverage | 37/108 (34.3%) | 25/111 (22.5%) |
| Returned recommendations | 108 | 111 |
| Direct / related / stretch | 7 / 17 / 11 | 5 / 15 / 5 |
| Unrelated / uncertain / unassessed / mapping-unscored | 0 / 2 / 68 / 3 | 0 / 0 / 83 / 3 |
| Ordinary abstentions | 1/36 (2.8%) | 0/36 (0.0%) |
| Naming controls conforming | 3/4 (75.0%) | 3/4 (75.0%) |
| Failed executions | 0 | 0 |
| Invalid candidate judgments | 0 | 0 |
| Pattern fallbacks | 4 | 3 |
| Query plans: generated / fallback / baseline | 34 / 2 / 4 | 35 / 2 / 3 |
| Mean question latency (seconds) | 209.5 | 246.5 |
| Median question latency (seconds) | 227.1 | 262.2 |
| P95 question latency (seconds) | 267.3 | 316.9 |
| LLM calls | 3225 | 3334 |
| Recorded API tokens | 3785403 | 3733705 |

Recall uses the same 35 eligible ordinary questions and 668 positive targets in both runs. `lcrec-v2-008-descriptive` is excluded from official recall because three returned recommendations fail its technical-source restriction in both runs; this is a mapping/source failure, not an execution failure or an abstention. Its prompt uses `Using "filename.pdf"`, whereas the existing production detector recognizes the `according to "filename.pdf"` structure. No source-parser change was made in this experiment.

Precision relevance bounds over all recommendations: 32.4%–100.0% previously and 22.5%–100.0% now. These are incomplete-label bounds, not confidence intervals. The new [pending-review file](pending_review.jsonl) exports 83 unassessed recommendation occurrences; absence of a label does not establish irrelevance.

Mean question latency rises 17.7%, model calls rise 3.4%, and recorded API tokens change -1.4%. Latency is descriptive: service/network timing and unseeded generation differ between runs. Token telemetry is not an Azure billing total.

## Annotated-target overlap by stage

This is raw identity/body overlap against annotated targets, not exhaustive semantic relevance. It includes the source-invalid question; official recommendation recall excludes it as described above.

| Stage | Previous: question hits | New: question hits | Previous: matched targets | New: matched targets |
|---|---:|---:|---:|---:|
| merged_candidates | 35/36 (97.2%) | 34/36 (94.4%) | 245/670 (36.6%) | 192/670 (28.7%) |
| chunk_shortlist | 26/36 (72.2%) | 26/36 (72.2%) | 99/670 (14.8%) | 70/670 (10.4%) |
| final_context | 18/36 (50.0%) | 21/36 (58.3%) | 37/670 (5.5%) | 35/670 (5.2%) |
| recommendations | 18/36 (50.0%) | 15/36 (41.7%) | 35/670 (5.2%) | 25/670 (3.7%) |

## What the traces show

The merged pool contains fewer annotated targets (245 → 192), while the number of questions with a target somewhere in the four-problem final context rises (18 → 21). The final three-problem output then loses several of these hits. This is a combination of candidate coverage and final ordering; successful pattern extraction alone does not ensure a useful recommendation.

### Fourth-place targets omitted by the recommendation limit

The following five **scorable** ordinary questions have a known-positive problem at context position four and no known positive in the three returned recommendations. The same raw behavior also occurs for `lcrec-v2-008-descriptive`, but that source-unscored question is excluded from this table. These are annotated targets, not proof that the first three suggestions are irrelevant.

| Question | Known-positive fourth problem | Returned problem numbers |
|---|---:|---|
| lcrec-v2-002-descriptive | 3613 | 1514, 3123, 3772 |
| lcrec-v2-007-short | 1606 | 61, 1882, 3354 |
| lcrec-v2-010-descriptive | 2722 | 2394, 2227, 2756 |
| lcrec-v2-011-descriptive | 2363 | 2394, 1633, 1587 |
| lcrec-v2-014-descriptive | 1489 | 2378, 3419, 2359 |

### Some generalizations discard useful structure

For `lcrec-v2-014-short` (maximum-spanning-tree dependency parsing), one generated operation query is:

> Given a list of candidate edges and their weights, choose a subset of edges (with no extra constraints) whose total weight is as large as possible.

This query drops the tree constraint. Other traces retain housekeeping tasks such as storing an already computed value. These are observed signs that operation decomposition can overgeneralize despite the prompt safeguards. The full original source remains available to judging, but this does not make every search query useful.

Conversely, the new run gains confirmed hits for keyed grouping (`lcrec-v2-011-short`) and grammar-rule combination (`lcrec-v2-013-descriptive`). Outcomes are mixed across topics and wordings; the table below preserves the full comparison.

## Per-question comparison

D=direct, R=related, S=stretch, X=unrelated, ?=uncertain, U=unassessed, !=mapping-unscored.

| Question | Previous recommendations | New recommendations | Previous hit → new hit |
|---|---|---|---|
| lcrec-v2-001-short | abstain | 2642 (D), 1514 (S), 2359 (U) | no → yes |
| lcrec-v2-001-descriptive | 1786 (R), 2699 (R), 2642 (D) | 2096 (U), 863 (U), 2359 (U) | yes → no |
| lcrec-v2-002-short | 1489 (U), 3553 (U), 3613 (R) | 3613 (R), 2203 (U), 3547 (U) | yes → yes |
| lcrec-v2-002-descriptive | 3419 (?), 2203 (U), 3650 (U) | 1514 (U), 3123 (U), 3772 (U) | no → no |
| lcrec-v2-003-short | 1959 (U), 480 (U), 3645 (U) | 1685 (U), 2599 (U), 56 (U) | no → no |
| lcrec-v2-003-descriptive | 2587 (U), 1331 (U), 3321 (U) | 3907 (U), 1959 (U), 2845 (U) | no → no |
| lcrec-v2-004-short | 3663 (U), 3852 (U), 3003 (U) | 1130 (U), 1022 (U), 2673 (U) | no → no |
| lcrec-v2-004-descriptive | 2671 (U), 49 (U), 988 (U) | 528 (U), 83 (U), 1313 (U) | no → no |
| lcrec-v2-005-short | 1947 (D), 2323 (U), 3276 (R) | 1253 (U), 2397 (U), 1975 (U) | yes → no |
| lcrec-v2-005-descriptive | 3476 (U), 1947 (D), 1066 (D) | 1947 (D), 1937 (U), 3276 (R) | yes → yes |
| lcrec-v2-006-short | 528 (D), 497 (R), 2587 (U) | 381 (R), 710 (R), 380 (R) | yes → yes |
| lcrec-v2-006-descriptive | 528 (D), 2599 (U), 382 (R) | 528 (D), 3585 (U), 69 (U) | yes → yes |
| lcrec-v2-007-short | 1606 (R), 173 (U), 641 (S) | 61 (U), 1882 (U), 3354 (U) | yes → no |
| lcrec-v2-007-descriptive | 61 (U), 1882 (U), 1656 (U) | 2757 (S), 555 (U), 708 (U) | no → yes |
| lcrec-v2-008-short | 1157 (U), 308 (U), 3195 (U) | 1669 (U), 1779 (U), 3225 (U) | no → no |
| lcrec-v2-008-descriptive | 3578 (!), 3003 (!), 3929 (!) | 1465 (!), 3394 (!), 391 (!) | no → no |
| lcrec-v2-009-short | 271 (S), 717 (R), 1256 (S) | 393 (R), 717 (R), 779 (U) | yes → yes |
| lcrec-v2-009-descriptive | 393 (R), 3023 (U), 271 (S) | 393 (R), 717 (R), 1238 (U) | yes → yes |
| lcrec-v2-010-short | 3058 (U), 1158 (U), 1892 (U) | 1158 (U), 2227 (U), 3481 (U) | no → no |
| lcrec-v2-010-descriptive | 3497 (U), 1892 (U), 3808 (U) | 2394 (U), 2227 (U), 2756 (U) | no → no |
| lcrec-v2-011-short | 1817 (U), 1113 (U), 2329 (U) | 2631 (U), 1484 (R), 1587 (U) | no → yes |
| lcrec-v2-011-descriptive | 3214 (U), 1336 (U), 3230 (U) | 2394 (U), 1633 (U), 1587 (U) | no → no |
| lcrec-v2-012-short | 3204 (R), 2275 (R), 2980 (S) | 2634 (U), 1893 (U), 1868 (U) | yes → no |
| lcrec-v2-012-descriptive | 2461 (U), 2901 (U), 3117 (S) | 3117 (S), 2275 (R), 2634 (U) | yes → yes |
| lcrec-v2-013-short | 1297 (U), 2609 (U), 1593 (U) | 986 (U), 30 (U), 300 (U) | no → no |
| lcrec-v2-013-descriptive | 2953 (U), 3579 (U), 1520 (U) | 756 (R), 3349 (U), 2807 (U) | no → yes |
| lcrec-v2-014-short | 3600 (S), 1489 (R), 2378 (U) | 685 (U), 3543 (U), 3419 (U) | yes → no |
| lcrec-v2-014-descriptive | 2378 (U), 685 (U), 1489 (R) | 2378 (U), 3419 (U), 2359 (U) | yes → no |
| lcrec-v2-015-short | 1441 (S), 150 (R), 241 (U) | 225 (U), 232 (U), 1441 (S) | yes → yes |
| lcrec-v2-015-descriptive | 1441 (S), 150 (R), 1381 (S) | 1441 (S), 1172 (U), 1825 (U) | yes → yes |
| lcrec-v2-016-short | 1348 (U), 147 (U), 1656 (U) | 3500 (U), 3271 (U), 3161 (U) | no → no |
| lcrec-v2-016-descriptive | 708 (U), 2811 (U), 88 (U) | 659 (U), 21 (U), 1669 (U) | no → no |
| lcrec-v2-017-short | 1188 (D), 1116 (U), 1226 (U) | 1188 (D), 622 (R), 641 (R) | yes → yes |
| lcrec-v2-017-descriptive | 622 (R), 641 (R), 1882 (U) | 1188 (D), 641 (R), 1172 (U) | yes → yes |
| lcrec-v2-018-short | 3923 (U), 1828 (U), 1515 (?) | 3063 (U), 1194 (U), 1357 (U) | no → no |
| lcrec-v2-018-descriptive | 3030 (S), 3923 (U), 26 (U) | 1282 (U), 49 (U), 1357 (U) | yes → no |
| lcrec-v2-019-short | abstain | abstain | control |
| lcrec-v2-019-descriptive | abstain | abstain | control |
| lcrec-v2-020-short | abstain | abstain | control |
| lcrec-v2-020-descriptive | 2157 (U), 30 (U), 1203 (U) | 2628 (U), 288 (U), 57 (U) | control |

## Scope and limitations

V2 is a development benchmark used for iteration, not held-out evidence of generalization. One unseeded run against a historical baseline cannot isolate code effects from generation/service variation; technical query expansion also remains stochastic. Fixed labels are incomplete, so these scores measure confirmed annotated overlap rather than the semantic quality of all new recommendations. No evaluation LLM, label expansion, source-parser fix, reranking-limit change, or recommendation-limit change was introduced for this run. The feature includes passing the source-mechanism description to the existing conceptual judge and clarifying that it must be checked against the original prose. The same literal-naming control (`lcrec-v2-020-descriptive`) remains nonconformant.

Earlier v1/v2 reports and the shortlist experiment are preserved. `config.yml` is restored to the standard v2 results directory, with shortlist **30** retained as requested. The new report lives separately here.
