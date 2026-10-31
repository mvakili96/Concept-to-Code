# LeetCode recommendation results

The [final v2 title-selection report](v2/summary.md) covers all 40 questions with zero execution or source-validation failures. It reports assessed precision, hit rate, macro Capped Recall@k, label coverage, and supporting diagnostics. [Metric definitions](../../evaluation-data/METRICS.md).

- [summary.md](v2/summary.md): scores, settings, and per-question results.
- [per_question.csv](v2/per_question.csv): tabular results and individual capped-recall scores.
- [details.json](v2/details.json): predictions, intermediate stages, labels, and execution provenance.
- [pending_review.jsonl](v2/pending_review.jsonl): recommendations without frozen relevance labels.

The 40 records combine 33 original evaluations, five recovered evaluations, and two source-corrected evaluations. Timings aggregate several execution segments. Header settings describe the latest segment, and each question retains its original run ID.

Both [benchmark dataset versions](../../evaluation-data/leetcode-recommendation/) are retained. Earlier result files are archived locally under the ignored `diagnostics/` directory. Only this final result is published.
