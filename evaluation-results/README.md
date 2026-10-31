# Evaluation results

[Benchmark contents and sample structure](../evaluation-data/README.md) · [Metric formulas, relevance labels, and recall interpretation](../evaluation-data/METRICS.md)

- [document-qa/](document-qa/): document evidence-text precision/recall and generated QA answers.
- [leetcode-recommendation/](leetcode-recommendation/): separate [v1](leetcode-recommendation/v1/) and [v2](leetcode-recommendation/v2/) reports with assessed precision, hit rate, macro Capped Recall@k, coverage, controls, failures and runtime. Full annotated-target recall is retained as a secondary diagnostic.

Scripts overwrite only their configured completed report files. Configure another results directory to retain an experiment. LeetCode checkpoints are local and ignored. The v1 baseline is explicitly marked as imported historical inference.

Saved reports retain their original paths, configuration keys and code fingerprints as historical inference metadata. Capped recall was added offline without new inference. Its reporting provenance is separate from the original run metadata. Current commands and configuration names are documented in the root README.
