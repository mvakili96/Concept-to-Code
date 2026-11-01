# Evaluation results

[Benchmark contents and sample structure](../evaluation-data/README.md) · [Metric formulas, relevance labels, and recall interpretation](../evaluation-data/METRICS.md)

- [document-qa/](document-qa/): document evidence-text precision/recall and saved generated answers.
- [document-qa/judge-validation/](document-qa/judge-validation/summary.md): the latest judge on 48 cases in two runs, with exact agreement, consistency, and errors. The 30 development and 18 reserved cases remain identified.
- [leetcode-recommendation/v2/](leetcode-recommendation/v2/): the final title-selection report with assessed precision, hit rate, macro Capped Recall@k, coverage, controls, failures and runtime. Full annotated-target recall is retained as a secondary diagnostic. Both benchmark dataset versions remain in `evaluation-data/`.

Scripts overwrite only their configured completed report files. Superseded experiments and older judge-only answer scores are archived locally under the ignored `diagnostics/` directory. Runtime checkpoints are local and ignored. Optional `evaluate_qa_answers.py` writes new answer-quality judgments to `document-qa/answers/` when run, using the latest judge.

Saved reports retain their original paths, configuration keys and code fingerprints as historical inference metadata. Capped recall was added offline without new inference. Its reporting provenance is separate from the original run metadata. Current commands and configuration names are documented in the root README.
