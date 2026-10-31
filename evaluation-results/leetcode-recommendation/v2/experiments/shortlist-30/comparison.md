# V2 shortlist-depth experiment

**Offline metric update:** Capped Recall@3 averages each eligible question's target hits divided by `min(3, positive target count)`. Match, Relevant, and Stretch count when in the annotated target set. Saved predictions and original inference metadata are unchanged. The original recall discussion below refers to full annotated-target recall, now a secondary diagnostic. Eligible question counts: 36 / 35.

Changed only `related_problem.conceptual_reranking.shortlist_top_k` from **20 to 30**. Both runs use the same production code, PDFs, index artifacts, 40 questions, 360 frozen pair labels, Azure deployment and two-worker configuration. Final recommendation limit remains three. The baseline report is preserved.

- Baseline run: `378629f00d9044e4b0225d5a7751bb68`
- Experiment run: `229b9e1c80d54e398b63d8f4d81c08f2`

| Metric | Shortlist 20 | Shortlist 30 |
|---|---:|---:|
| Assessed precision | 26/27 (96.3%) | 35/35 (100.0%) |
| Confirmed hit rate | 15/36 (41.7%) | 18/36 (50.0%) |
| Hit-rate upper bound | 35/36 (97.2%) | 35/36 (97.2%) |
| Capped recall@3 (macro) | 24.1% | 33.3% |
| Full annotated-target recall (secondary) | 26/670 (3.9%) | 35/668 (5.2%) |
| Label coverage | 28/108 (25.9%) | 37/108 (34.3%) |
| Returned recommendations | 108 | 108 |
| Unrelated / uncertain / unassessed / mapping-unscored | 1 / 1 / 80 / 0 | 0 / 2 / 68 / 3 |
| Ordinary abstentions | 1/36 (2.8%) | 1/36 (2.8%) |
| Naming controls conforming | 3/4 (75.0%) | 3/4 (75.0%) |
| Failed executions | 0 | 0 |
| Invalid candidate judgments | 0 | 0 |
| Pattern fallbacks | 4 | 4 |
| Mean question latency (seconds) | 141.9 | 209.5 |
| LLM calls | 2241 | 3225 |
| Recorded API tokens | 2641624 | 3785403 |

The official recall excludes questions with unscored recommendation mappings: 36 ordinary questions were eligible at shortlist 20, and 35 at shortlist 30. On the **same 35 jointly scored questions**, recall is **26/668 (3.9%) → 35/668 (5.2%)**. Three recommendations from the excluded question remain explicitly unscored, not irrelevant or absent.

Observed gains are modest: three more ordinary questions have a confirmed relevant recommendation, and nine more annotated targets are recommended. Mean question latency rises **47.6%**, model calls **43.9%**, and recorded tokens **43.3%**. The 100% assessed precision covers only 35 definitively labeled recommendations out of 108 returns; it is not 100% overall recommendation quality. Overall relevance-precision bounds are 24.1%–99.1% at 20 and 32.4%–100% at 30.

## Source-restriction issue

All three mapping failures occur on `lcrec-v2-008-descriptive`. Its prompt says `Using "Grokking-the-system-design-interview-free.pdf"`, but the production source detector recognizes only the `according to "exact filename.pdf"` structure (`main.py`, `find_explicit_sources`). Both runs searched all technical sources for this question. At shortlist 30 all technical passages came from Computer Vision, and the evaluator correctly rejected the recommendations' evidence as outside the allowed source. The parameter experiment does not fix this existing source-selection limitation.

Both runs also fail the same literal-naming control, `lcrec-v2-020-descriptive`: they recommend problems instead of abstaining. No production changes were made to address it during this experiment.

## Annotated-target overlap by stage

Overlap measures the frozen annotated targets, not exhaustive semantic relevance. This stage table reports raw identity/body overlap, matching the evaluator's secondary diagnostics. It includes the source-invalid question, whereas official recommendation recall above excludes it.

| Stage | 20: question hits | 30: question hits | 20: matched targets | 30: matched targets |
|---|---:|---:|---:|---:|
| merged_candidates | 34/36 (94.4%) | 35/36 (97.2%) | 239/670 (35.7%) | 245/670 (36.6%) |
| chunk_shortlist | 22/36 (61.1%) | 26/36 (72.2%) | 67/670 (10.0%) | 99/670 (14.8%) |
| final_context | 16/36 (44.4%) | 18/36 (50.0%) | 31/670 (4.6%) | 37/670 (5.5%) |
| recommendations | 15/36 (41.7%) | 18/36 (50.0%) | 26/670 (3.9%) | 35/670 (5.2%) |

## Per-question changes

D=direct, R=related, S=stretch, X=unrelated, ?=uncertain, U=unassessed, !=mapping-unscored.

| Question | Shortlist 20 | Shortlist 30 |
|---|---|---|
| lcrec-v2-001-short | abstain | abstain |
| lcrec-v2-001-descriptive | 1810 (R), 3651 (R), 3596 (R) | 1786 (R), 2699 (R), 2642 (D) |
| lcrec-v2-002-short | 2493 (U), 3789 (U), 1547 (U) | 1489 (U), 3553 (U), 3613 (R) |
| lcrec-v2-002-descriptive | 3547 (U), 2642 (U), 3924 (U) | 3419 (?), 2203 (U), 3650 (U) |
| lcrec-v2-003-short | 3555 (U), 3422 (U), 2470 (U) | 1959 (U), 480 (U), 3645 (U) |
| lcrec-v2-003-descriptive | 2080 (U), 506 (R), 3945 (U) | 2587 (U), 1331 (U), 3321 (U) |
| lcrec-v2-004-short | 3663 (U), 3005 (U), 2641 (U) | 3663 (U), 3852 (U), 3003 (U) |
| lcrec-v2-004-descriptive | 3663 (U), 3318 (U), 3541 (U) | 2671 (U), 49 (U), 988 (U) |
| lcrec-v2-005-short | 2323 (U), 1057 (R), 3693 (U) | 1947 (D), 2323 (U), 3276 (R) |
| lcrec-v2-005-descriptive | 3476 (U), 1947 (D), 2323 (U) | 3476 (U), 1947 (D), 1066 (D) |
| lcrec-v2-006-short | 398 (R), 2191 (U), 2699 (U) | 528 (D), 497 (R), 2587 (U) |
| lcrec-v2-006-descriptive | 528 (D), 381 (R), 497 (R) | 528 (D), 2599 (U), 382 (R) |
| lcrec-v2-007-short | 1606 (R), 2747 (U), 1656 (U) | 1606 (R), 173 (U), 641 (S) |
| lcrec-v2-007-descriptive | 2757 (S), 2515 (U), 3354 (U) | 61 (U), 1882 (U), 1656 (U) |
| lcrec-v2-008-short | 1828 (U), 2013 (U), 3624 (U) | 1157 (U), 308 (U), 3195 (U) |
| lcrec-v2-008-descriptive | 3271 (U), 3710 (U), 3195 (U) | LeetCode_4000_Problem_Reference.pdf::page=1791::problem=3578 (!), LeetCode_4000_Problem_Reference.pdf::page=1502::problem=3003 (!), LeetCode_4000_Problem_Reference.pdf::page=1966::problem=3929 (!) |
| lcrec-v2-009-short | 2526 (U), 385 (U), 3023 (U) | 271 (S), 717 (R), 1256 (S) |
| lcrec-v2-009-descriptive | 67 (X), 369 (U), 1734 (U) | 393 (R), 3023 (U), 271 (S) |
| lcrec-v2-010-short | 1817 (U), 1500 (U), 1892 (U) | 3058 (U), 1158 (U), 1892 (U) |
| lcrec-v2-010-descriptive | 3063 (U), 2227 (U), 1948 (U) | 3497 (U), 1892 (U), 3808 (U) |
| lcrec-v2-011-short | 1113 (U), 1934 (U), 3808 (U) | 1817 (U), 1113 (U), 2329 (U) |
| lcrec-v2-011-descriptive | 1336 (U), 3808 (U), 3521 (U) | 3214 (U), 1336 (U), 3230 (U) |
| lcrec-v2-012-short | 2275 (R), 2823 (U), 3653 (U) | 3204 (R), 2275 (R), 2980 (S) |
| lcrec-v2-012-descriptive | 2901 (U), 3117 (S), 2411 (S) | 2461 (U), 2901 (U), 3117 (S) |
| lcrec-v2-013-short | 1593 (U), 1520 (U), 3298 (U) | 1297 (U), 2609 (U), 1593 (U) |
| lcrec-v2-013-descriptive | 2311 (U), 2914 (U), 97 (U) | 2953 (U), 3579 (U), 1520 (U) |
| lcrec-v2-014-short | 3600 (S), 685 (U), 2374 (U) | 3600 (S), 1489 (R), 2378 (U) |
| lcrec-v2-014-descriptive | 685 (U), 2378 (U), 2360 (U) | 2378 (U), 685 (U), 1489 (R) |
| lcrec-v2-015-short | 1441 (S), 1597 (R), 32 (S) | 1441 (S), 150 (R), 241 (U) |
| lcrec-v2-015-descriptive | 1441 (S), 946 (S), 1381 (S) | 1441 (S), 150 (R), 1381 (S) |
| lcrec-v2-016-short | 708 (U), 147 (U), 109 (U) | 1348 (U), 147 (U), 1656 (U) |
| lcrec-v2-016-descriptive | 295 (U), 1902 (U), 26 (U) | 708 (U), 2811 (U), 88 (U) |
| lcrec-v2-017-short | 1188 (D), 1670 (U), 622 (R) | 1188 (D), 1116 (U), 1226 (U) |
| lcrec-v2-017-descriptive | 1188 (D), 1670 (U), 641 (R) | 622 (R), 641 (R), 1882 (U) |
| lcrec-v2-018-short | 1515 (?), 1828 (U), 780 (U) | 3923 (U), 1828 (U), 1515 (?) |
| lcrec-v2-018-descriptive | 3923 (U), 2090 (U), 25 (U) | 3030 (S), 3923 (U), 26 (U) |
| lcrec-v2-019-short | abstain | abstain |
| lcrec-v2-019-descriptive | abstain | abstain |
| lcrec-v2-020-short | abstain | abstain |
| lcrec-v2-020-descriptive | 734 (U), 1583 (U), 49 (U) | 2157 (U), 30 (U), 1203 (U) |

## Interpretation limits

V2 is now used for parameter selection, so these are **development comparisons**, not held-out generalization. This is one new run against an earlier baseline: Azure generation is unseeded and timings are not contemporaneous, so not every difference can be attributed to shortlist size. No relevance labels were changed after observing predictions. Unseen pairs remain unassessed; assessed precision and confirmed hit rate must be read alongside label coverage and their bounds. Tokens omit any interrupted/in-flight SDK activity and are not billing totals.

The original v2/shortlist-20 configuration is restored after execution. The interrupted v1 attempt is not used in this comparison.
