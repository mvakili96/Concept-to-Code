# Title-first selection: five-question comparison

**Offline metric update:** Capped Recall@3 averages each eligible question's target hits divided by `min(3, positive target count)`. Match, Relevant, and Stretch count when in the annotated target set. Saved predictions and original inference metadata are unchanged. The original recall discussion below refers to full annotated-target recall, now a secondary diagnostic. Eligible question counts: 5 / 5.

Five v2 benchmark questions were selected before inference: the first ordinary short-wording question for each distinct technical PDF, in benchmark order. Production settings were retained; only the results directory was overridden in memory. The saved retrieval-mode comparison uses exactly these same question texts, reference-file hashes and PDF hashes.

| Metric | Previous retrieval (shortlist 30) | Title-first (shortlist up to 20) |
|---|---:|---:|
| Assessed precision | 5/5 (100.0%) | 4/4 (100.0%) |
| Hit rate | 2/5 (40.0%) | 3/5 (60.0%) |
| Capped recall@3 (macro) | 33.3% | 26.7% |
| Full annotated-target recall (secondary) (micro) | 5/113 (4.4%) | 4/113 (3.5%) |
| Label coverage | 5/12 (41.7%) | 4/7 (57.1%) |
| Recommendations | 12 | 7 |
| Abstentions | 1 | 1 |
| Execution failures | 0 | 0 |
| Mean question latency | 210.8 s | 26.3 s |
| LLM calls | 408 | 19 |
| Recorded API tokens | 471416 | 224111 |

Precision includes direct, related and stretch frozen labels. Unknown recommendations are unassessed, excluded from assessed precision and retained in label-coverage and usefulness bounds. The four assessed title-first recommendations comprise one related-practice and three stretch labels, with no direct matches or labeled unrelated items. Three further recommendations are unassessed. Thus 100% assessed precision does not establish that every returned recommendation is useful; the all-return usefulness bounds are 57.1%–100%.

Annotated-target recall is overlap with the 113 incomplete annotated positive targets for these five topics. It measures named target coverage, not semantic correctness or exhaustive recall. Returning at most three per question also limits achievable target coverage.

## Per-question comparison

R=related practice, S=stretch, U=unassessed. These are frozen benchmark labels, not the production model's own connection grades.

| Topic / ID | Previous recommendations | Title-first recommendations | Previous / title-first target hits | Previous / title-first seconds |
|---|---|---|---:|---:|
| Dijkstra contour tracing / `lcrec-v2-001-short` | Abstain | Abstain | 0 / 0 | 6.5 / 31.8 |
| Frequency-sensitive coding / `lcrec-v2-004-short` | 3663 (U), 3852 (U), 3003 (U) | 820 (S), 451 (U), 791 (U) | 0 / 1 | 243.1 / 39.8 |
| Round-robin dispatch / `lcrec-v2-007-short` | 1606 (R), 173 (U), 641 (S) | 1606 (R), 622 (S) | 2 / 2 | 223.1 / 17.1 |
| Variable-length integers / `lcrec-v2-009-short` | 271 (S), 717 (R), 1256 (S) | 1256 (S) | 3 / 1 | 318.2 / 15.5 |
| CKY recognition / `lcrec-v2-013-short` | 1297 (U), 2609 (U), 1593 (U) | 72 (U) | 0 / 0 | 262.8 / 27.1 |

## Observations and limits

- Frequency-sensitive coding gained a labeled hit through problem 820; its other two returns, 451 and 791, are unassessed.
- Round-robin dispatch returned 1606 and 622; both have positive reference labels.
- Integer encoding returned 1256, retaining one of the previous three positive targets.
- Dijkstra contour tracing still abstained: the technical retrieval missed the requested method, so the title proposal was empty.
- CKY returned 72 (Edit Distance), whose relevance to this topic is unassessed; this is not counted as a confirmed hit.
- All five executions and all seven recommendation identity/quote mappings passed. The nine selection calls passed on their first attempts, without application-level rate-limit or validation retries.
- All five technical answers hit the existing 400-token output cap. Original technical evidence was supplied separately to both selector passes; no output budget was changed for this experiment.
- No naming controls, descriptive wordings or full benchmark were run. This small development comparison supports a latency improvement and one additional confirmed question hit; it does not establish overall relevance improvement or generalization.

[Full subset report](summary.md) · [Per-question output](per_question.csv) · [Structured details](details.json) · [Unassessed recommendations](pending_review.jsonl)
