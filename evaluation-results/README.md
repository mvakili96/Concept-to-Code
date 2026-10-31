# Evaluation results

[Benchmark contents and sample structure](../evaluation-data/README.md) · [Metric formulas, relevance labels, and recall interpretation](../evaluation-data/METRICS.md)

- [document-qa/](document-qa/): document evidence-text precision/recall and generated QA answers.
- [leetcode-recommendation/v2/](leetcode-recommendation/v2/): the final title-selection report with assessed precision, hit rate, macro Capped Recall@k, coverage, controls, failures and runtime. Full annotated-target recall is retained as a secondary diagnostic. Both benchmark dataset versions remain in `evaluation-data/`.

Scripts overwrite only their configured completed report files. Earlier LeetCode results are archived locally under the ignored `diagnostics/` directory. LeetCode checkpoints are local and ignored.

Saved reports retain their original paths, configuration keys and code fingerprints as historical inference metadata. Capped recall was added offline without new inference. Its reporting provenance is separate from the original run metadata. Current commands and configuration names are documented in the root README.
