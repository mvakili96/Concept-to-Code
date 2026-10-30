# Evaluation results

- [document-qa/](document-qa/): document evidence-text precision/recall and generated QA answers.
- [leetcode-recommendation/](leetcode-recommendation/): separate [v1](leetcode-recommendation/v1/) and [v2](leetcode-recommendation/v2/) reports with recommendation precision, hit rate, annotated-target recall, coverage, controls, failures and runtime.

Scripts overwrite only their configured completed report files. Configure another results directory to retain an experiment. LeetCode checkpoints are local and ignored; the v1 baseline is explicitly marked as imported historical inference.

Saved reports retain their original paths, configuration keys and code fingerprints as historical run metadata. Current commands and configuration names are documented in the root README.
