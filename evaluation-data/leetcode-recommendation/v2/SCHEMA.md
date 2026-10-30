# Fresh-topic schema

Question/reference schema is `1.0.0`, compatible with the existing LeetCode evaluator. Benchmark version is `2.0.0`. IDs begin `lcrec-v2-`; they must remain stable in later experiments.

## Questions and shared references

Each JSONL question contains `id`, `topic_id`, `question`, `wording`, `kind`, `allowed_technical_sources`, `expected_behavior`, `origin_batch`, `difficulty` and `tags`. The two wordings have the same topic-level relevance conditions and source restrictions. Difficulty is a qualitative authoring label, not measured model performance.

Shared `topics` store `name`, `mechanism`, source restrictions, exact `technical_evidence`, optional explicit-literal `control`, positive `target_problem_numbers`, `screening_patterns` and `corpus_scan`. Evidence has a stable ID, exact filename, one-based physical PDF page, zero-based `[start,end_exclusive)` offsets and the original quote. Printed page labels are not used. Source prose is used without interpreting figures, captions, tables, or scanned content.

`pairs` are indexed by `topic_id::lcNUMBER`. They contain source-owned problem number/title/difficulty, physical page, body bounds, exact `problem_evidence`, linked technical evidence IDs, relevance label, rationale, limitation and automated review provenance. SQL-related references quote the task's prose rather than schema definitions or example rows. No problem identity, solution or relationship is taken from an answering model's prediction.

Labels retain the existing direct/related/stretch/unrelated/uncertain meanings. A connection is an explicitly limited interpretation of a shared task or operation; the label does not claim an identical textbook implementation. `source_audited` and `codex_source_audit` mean automated source checks and semantic review by the coding assistant. `human_reviewed` is false; the exact serving model identifier is unavailable. Occurrence checks alone are not semantic proof.

All positive pairs are included in `target_problem_numbers`; negatives and uncertain pairs are excluded. Absent pairs retain the evaluator's `unassessed` behavior. A complete text scan must not enable an implicit-negative policy: `full_semantic_negative_audit` is explicitly false.

## Full-corpus scan and novelty records

The shared catalogue has exactly the problem numbers 1–4000, their source/page/body bounds and SHA256 of the exact extracted body. Statements were discovered from original headings, not a selected list of current retrieval chunks.

Each ledger row covers a contiguous 100-problem range for one topic and records its body checksum, full-statement pattern matches, and separately the individually source-audited identities. Every topic has exactly 40 non-overlapping ranges. Both questions share the topic scan. All statements are considered; no score ranking or top-k limits the scan. `semantic_negative_judgment:false` means a nonmatch has not automatically received a negative relevance label.

`question_freeze_v2.json` stores source mechanisms, question text and production code/configuration fingerprints. Source-anchoring corrections during preparation do not involve production predictions. `NOVELTY_AUDIT_v2.json` records the prior-topic inventory, prior QA questions, checked input fingerprints and an individual primary-topic novelty rationale. Topics can share general primitives and public problem identities. This is not proof of novelty relative to unknown private history or model pretraining.

## Verification and future evaluation

The corpus manifest pins all original PDFs, questions/references and preparation artifacts. `verify_dataset.py` independently checks original quotes, page positions, identities and body hashes, all 80,000 topic/statement scan decisions, coverage ranges, naming controls, and inclusion of every annotated positive in the recall targets. It runs no production inference.

Future evaluation uses only recommendations actually rendered by production, with verified identities and within-question deduplication. Precision excludes uncertain/unassessed/invalidly mapped items and must be accompanied by coverage. Recall is against the positively annotated references, not a guarantee of recovering every semantically relevant problem in the book. With three output slots, `min(3,R)/R` is the maximum recall for a topic with R references; report the corresponding aggregate ceiling. Controls are scored by explicit requirement conformance, not ordinary positive recall. Failed executions are not abstentions.

Existing reports belong to earlier datasets and must not be relabeled as v2 results. The new questions have not been used for production tuning or evaluation during preparation. After they guide changes, their untouched-first-evaluation status ends.
