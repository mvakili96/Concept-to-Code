# Evaluation metric definitions

[Benchmark structure and sample contents](README.md) · [Document-QA evaluator](../evaluate_document_qa.py) · [LeetCode evaluator](../evaluate_leetcode_recommendation.py)

The current metrics are deterministic comparisons against saved references. Production LLMs still generate expansions, answers, and recommendation judgments, but their own opinions are not the evaluation ground truth. Answer correctness and faithfulness are not scored.

## Document QA: evidence text precision and recall

These metrics compare the **final reranked context supplied to the answering LLM** with the dataset's specific evidence passages. They do not score the entire retrieval candidate pool or count how many chunks are relevant.

### Mapping text to PDF positions

For each question, the evaluator:

1. Normalizes reference and PDF text consistently for Unicode ligatures, case, whitespace, and line-break hyphenation.
2. Maps each reference quote to one unique consecutive sequence of normalized words on its cited source and physical page. Unordered vocabulary overlap is not sufficient.
3. Verifies every final chunk against its original PDF character slice and maps its complete words to positions on that page. Incomplete words at chunk boundaries are excluded.
4. Forms unions of the reference positions and context positions. Positions are identified by source, physical page, and normalized word index.

Two occurrences of the same word at different positions remain distinct. Overlapping chunks and repeated evidence count a position only once. Added formatting labels such as `SOURCE` and `PAGE` are excluded, while real PDF headings or other text present inside a chunk body remain in the context denominator.

### Per-question formulas

Let `E_q` be the union of annotated reference-evidence positions and `C_q` the union of final-context body-word positions.

```text
evidence text precision(q) = |E_q ∩ C_q| / |C_q|
evidence text recall(q)    = |E_q ∩ C_q| / |E_q|
```

Precision asks how much of the supplied context overlaps the annotations. Recall asks how much annotated text reached the final context. Identical words in a different source or page do not match.

The current implementation unions **all `evidence_records`**, including any annotated alternative passages. It does not choose the best alternative or calculate semantic satisfaction of `atomic_required_facts` or `required_evidence_groups`. Those fields document answer support and remain useful for inspection, but they are not separate scored metrics.

### Worked example from the saved QA report

For `ragbench-v1-001`, the Hough-transform question:

- Reference evidence has **101** unique word positions.
- Final context has **438** unique body-word positions.
- Their intersection has **101** positions.
- Precision is `101 / 438 = 23.1%`.
- Recall is `101 / 101 = 100%`.

The individual chunks contain 506 word occurrences before overlap is deduplicated. The denominator is 438, so overlap does not count twice. This is an example from the [saved report](../evaluation-results/document-qa/details.json), not a new inference run.

### Aggregation and exceptional cases

The reported corpus value is a **macro average**: calculate each question's score first, then average only questions with `status: scored`. Precision and recall maintain separate scored denominators. Word totals are not pooled across questions.

| Case | Precision | Recall |
|---|---|---|
| Valid mappings and nonempty context | Formula above | Formula above |
| Valid reference evidence, empty context | N/A | 0 |
| Unanswerable within allowed sources, with no positive evidence | N/A | N/A, even if context was retrieved |
| Missing, ambiguous, invalid, or failed text mappings | Unscored | Unscored |
| Pipeline execution fails | Unscored | Unscored |

Scored zeroes remain in averages. N/A and unscored cases are excluded and counted separately. In the current 50-question dataset, three controlled unanswerable questions normally receive N/A rather than retrieval-quality scores.

These are annotated-text overlap metrics, not semantic correctness. A valid alternative explanation or supporting passage can receive no overlap credit if it was not annotated.

## LeetCode relevance labels

There are **three positive relevance grades**, with additional labels and runtime statuses for other cases. Match, Relevant, and Stretch below are reader-friendly names. The stored enum values remain unchanged.

| Reader-friendly name | Stored reference label | Meaning | Counts as useful for precision, hit rate, and v2 recall? |
|---|---|---|---|
| **Match** | `direct_match` | The same computational task or a close specialization, with stated differences | Yes |
| **Relevant** | `related_practice` | A meaningful shared subproblem, operation, or data structure | Yes |
| **Stretch** | `stretch_connection` | A smaller but concrete transferable computational skill | Yes |
| Unrelated | `unrelated` | No defensible useful computational connection under the benchmark rubric | No |
| Uncertain | `uncertain` | The source audit could not confidently settle relevance | Excluded from assessed precision and positive targets |
| Unassessed | `unassessed` | No reference annotation exists for this topic/problem pair | Excluded from assessed precision and positive targets |
| Mapping-unscored | `unscored` | Runtime identity, quote, source, or passage verification failed | Excluded from assessed precision, with recall handling below |

Unrelated and uncertain are frozen reference labels. Unassessed and unscored describe evaluation outcomes. An unknown pair is not automatically wrong. A production model calling a recommendation a Match does not create a ground-truth Match label.

All three positive grades have equal credit in the current binary useful/not-useful metrics. Evaluation looks up the frozen pair label using the question's topic and the verified problem identity. It does not use the production model's displayed connection level as the reference label.

## LeetCode: units, formulas, and aggregation

Only problems **actually recommended to the user** are predictions. Retrieved candidates, internal accepted candidates, and context entries are not automatically recommendations. Duplicate problem identities count once within a question and count again when recommended for another question.

For a completed question `q`, define:

- `u_q`: returned recommendations verified and labeled Match, Relevant, or Stretch.
- `x_q`: returned recommendations verified and labeled unrelated.
- `n_q`: all unique returned recommendations, including uncertain, unassessed, and unscored items.
- `l_q`: returned recommendations with a frozen label, including uncertain.
- `T_q`: the explicit positive target set for the question's topic.
- `h_q`: distinct target identities in `T_q` actually recommended.
- `k`: the saved run's `related_problem.recommendation_validation.max_recommendations` setting, currently 3.
- `h_q@k`: distinct target identities in the first `k` unique recommendations, preserving their returned order.

### Assessed precision

```text
precision(q)       = u_q / (u_q + x_q)
assessed precision = Σ u_q / Σ (u_q + x_q)
```

The corpus score is **micro averaged over recommendations**, not the average of per-question precision scores. Completed records contribute to it. Uncertain, unassessed, and mapping-unscored items are excluded from this denominator. If no definitive items were assessed, precision is N/A.

Consequently, 100% assessed precision can coexist with incomplete label coverage. It establishes that every definitively assessed return was positive, not that every returned recommendation was useful.

### Hit rate

```text
hit(q)   = 1 if u_q > 0, otherwise 0
hit rate = ordinary completed questions with a hit / ordinary completed questions
```

A single Relevant or Stretch recommendation is sufficient for a hit. Match is not required. An all-unassessed output has no confirmed hit, but it has not been proven unrelated.

The 40-question v2 benchmark has 36 ordinary requests and four naming controls. Controls are evaluated separately. Failed executions are also excluded from the completed-question denominator and remain explicit failures. For example, a run with six failed ordinary questions reports hit rate over 30 completed ordinary questions. Confirmed hits per all 36 attempted ordinary questions can be reported alongside it to show end-to-end coverage.

### Capped Recall@k: headline recall

```text
capped recall@k(q) = h_q@k / min(k, |T_q|)
reported score    = mean(capped recall@k(q)) over eligible questions
```

This is a **macro average**, giving each eligible question equal weight. The denominator uses the configured recommendation budget, not the number of problems actually returned. With at least three annotated positives and `k = 3`, three positive returns score 100%, one scores 33.3%, and abstention scores 0%. If only two positive targets exist, recovering both scores 100%.

Match, Relevant, and Stretch all receive equal positive credit when they belong to the question's annotated target set. Unassessed and uncertain returns receive no annotated-hit credit, without being declared unrelated. Duplicate identities count once. Increasing the configured output budget changes `k`, so compare runs using the same cutoff.

This follows [BEIR's capped-recall definition](https://github.com/beir-cellar/beir/blob/main/beir/retrieval/custom_metrics.py). It measures annotated target recovery within a short recommendation budget. Labels remain incomplete, so valid unannotated alternatives may receive no credit. Both recall formulas are reported explicitly.

Eligibility is the same as for full target recall below. Controls and questions without positive targets are N/A. Execution failures and invalid mappings are unscored. A completed abstention with targets scores zero. N/A and unscored questions are excluded from the mean and counted separately.

The Markdown headline, JSON `metrics.capped_recall`, and CSV `capped_recall` column use this definition. JSON `capped_recall_by_question` and CSV columns also record each score's cutoff, status, matched-target count, capped denominator, and full target count.

### Full annotated-target recall: secondary diagnostic

```text
recall(q)               = h_q / |T_q|
annotated-target recall = Σ h_q / Σ |T_q|
```

This secondary corpus score is **micro averaged over target occurrences** in eligible ordinary questions. It retains the original calculation. The same topic's targets count once for each wording because each wording is a separate pipeline execution.

For current **v2, every positively annotated pair is in `T_q`**, including Match, Relevant, and Stretch. Unrelated, uncertain, and unlisted pairs are not positive targets. Historical v1 reports use their original smaller explicit target subset and retain those definitions.

Both recall metrics include completed ordinary questions with nonempty target sets and valid stage mappings. If any recommended item is mapping-unscored, the evaluator excludes that entire question from recall and reports the exclusion. Merely uncertain or unassessed returns do not exclude the question. A completed abstention gets recall 0 when targets exist. Controls and questions without positive targets have N/A recall.

The target list is incomplete semantic ground truth. This metric measures recovery of annotated identities, not every valid possible relationship across all 4,000 problems.

### Label coverage and controls

```text
label coverage = Σ l_q / Σ n_q
```

Coverage includes uncertain labels even though they are excluded from assessed precision. Unassessed and unscored returns remain in its denominator. Precision and coverage aggregate returns across completed records, including any returns on controls. Ordinary hit rate and recall exclude controls.

Each of the four v2 naming controls requires a literal method name in the problem statement and expects abstention in this corpus. Control conformance is completed controls returning no recommendation divided by completed controls. A failed control execution is a failure, not a correct abstention.

### Illustrative prediction scenarios

Suppose one ordinary question has five annotated targets: one Match, two Relevant, and two Stretch problems. These numbers illustrate the formulas and are not an extra benchmark record.

| Three returned problems | Assessed precision | Capped Recall@3 | Full target recall | Confirmed hit | Label coverage |
|---|---:|---:|---:|---:|---:|
| Relevant, Stretch, unrelated | 2/3 | 2/3 | 2/5 | Yes | 3/3 |
| Relevant, Stretch, unassessed | 2/2 | 2/3 | 2/5 | Yes | 2/3 |
| Three unassessed problems | N/A | 0/3 | 0/5 | No confirmed hit | 0/3 |
| No recommendations | N/A | 0/3 | 0/5 | No | N/A |

The Relevant and Stretch returns count toward recall in both first scenarios. They do not need to be direct matches. The second scenario's unassessed return does not become a false positive or an extra annotated hit.

## Current results and the full-recall ceiling

The [source-fixed collective report](../evaluation-results/leetcode-recommendation/v2/experiments/title-selection-full-source-fixed/source_fix.md) already counts all three positive grades:

- The references contain `21 Match + 180 Relevant + 134 Stretch = 335` positive topic/problem pairs.
- Their two wordings create `335 × 2 = 670` target occurrences across 36 ordinary questions.
- Recommendations hit `13 Match + 26 Relevant + 18 Stretch = 57` targets.
- Full annotated-target recall is therefore `57 / 670 = 8.5%`, retained as a secondary diagnostic.
- **Macro Capped Recall@3 is 54.6%**, averaging the 36 eligible ordinary questions. The four naming controls are N/A.
- The same report has hit rate `29 / 36 = 80.6%` because that metric asks whether each question received at least one useful recommendation.

The configured output cap is only **three recommendations per question**. Some topics have dozens of annotated positives, so a short useful list covers a small fraction of their targets. With 71 targets, even three annotated positive returns yield recall `3/71 = 4.2%`.

For this v2 benchmark and a three-problem cap, the maximum possible aggregate target coverage is:

```text
maximum annotated-target recall = Σ min(3, |T_q|) / Σ |T_q|
                                = 106 / 670
                                = 15.8%
```

Two quadtree questions have only two targets each, which makes the maximum numerator 106 rather than 108. This ceiling assumes valid mappings and selecting annotated targets for every output slot. Capped recall addresses this budget mismatch and can reach 100% without recommending every annotated target.

For the current predictions, the two quadtree questions each score `2/2`. The other 34 ordinary questions contribute 53 hits with denominator 3 each:

```text
macro capped recall@3 = (2/2 + 2/2 + 53/3) / 36 = 54.6%
```

Pooling capped counts would instead give `57/106 = 53.8%`. That is a micro calculation and is **not** the reported macro score.

Adding more relevance tiers to a positive definition can expand both its numerator and denominator, so it does not necessarily raise recall. Here all three tiers are already included. Hit rate captures whether at least one useful problem was found. Capped recall measures recovery within the recommendation budget, while full target recall records coverage of the larger annotation set.

Capped recall was added through an offline metric-reporting update to saved predictions. Original inference records, settings, labels, and target sets are preserved. The underlying composite report distinguishes retained results from targeted reruns. No new API calls were needed.
