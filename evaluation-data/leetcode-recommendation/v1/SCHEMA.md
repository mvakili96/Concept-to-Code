# LeetCode benchmark schema

Schema version: `1.0.0`. Current annotation/benchmark version: `1.1.0`; historical `1.0.0` references remain available. All 40 IDs form one fixed development benchmark for comparisons and ablations; there are no train/validation/test splits or held-out-generalization claims.

## Questions

Each JSONL record contains `id`, `topic_id`, exact `question`, `wording` (short/descriptive), `kind` (ordinary/explicit_naming_control), `allowed_technical_sources`, `expected_behavior` and `origin_batch`. The historical familiar/fresh origin is provenance, not a data split. Two questions can share a topic and references but are independently executed without conversation history.

The runtime calls `main.RAGPipeline.run_related_problem(question)` with the original question. Reference patterns or answers are never injected into that call.

## References

`topics` stores source restrictions, exact technical passages, physical pages, zero-based `[start, end_exclusive)` character offsets, original positive target numbers and optional control requirements. Additional autocomplete-frequency prose is explicitly anchored, not assumed to be covered by the original short evidence list.

`pairs` uses stable `topic_id::lcNUMBER` IDs. Each record has the exact source filename, physical page, source-owned number/title/difficulty, statement body bounds, exact `problem_evidence` quote and absolute page offsets, technical evidence links, rationale, limitation and review provenance. No reference depends on current chunk IDs. Full problem bodies are not duplicated in the published data.

The 173 broader-rubric labels are preserved. Seven previously reviewed positive targets are promoted using `direct`/`specialization` → `direct_match` and `shared_subproblem` → `related_practice`. Legacy weak/negative labels are not automatically imported into this broader rubric. Review fields distinguish automated source auditing from human approval; verification does not guarantee correctness.

Version 1.0 contains those 180 pairs, collected from earlier diagnostic outputs and original targets; it is a pooled assessment, not an exhaustive scan assigning a label to every problem. Version 1.1 preserves all 180 records and adds 72 source-audited pairs collected without reading prediction files. It has 252 labels in total, including eight uncertain pairs. The old five uncertain relationships are unchanged. See [COLLECTION.md](COLLECTION.md) for the limitations of post-hoc collection and automated semantic review.

New pairs retain the same required fields and add `discovery` (method, rank and score), `review_model`, `review_date`, and `verification_notes`. The top-level `annotation_provenance` identifies the base reference hash, collection plan/pool, reviewer scope and lack of human approval. `candidate_pool_v1_1.jsonl` records each collected pair's source-owned identity, physical page, body offsets, exact query and all discovery methods; it contains no relevance label or body text. `collection_manifest_v1_1.json` records the scan count, package versions, parsing rules, plan/collector/pool hashes and all-statement naming-control results. `corpus_manifest_v1_1.json` adds `annotation_artifact_sha256` and retains the source and runtime data hashes expected by the evaluator. No reference uses chunk IDs.

## Scoring

- Useful labels: `direct_match`, `related_practice`, `stretch_connection`. The latter can cover only a concrete component or prerequisite; differences must remain explicit.
- `unrelated` is a reviewed negative. `uncertain` is unresolved, not negative. A verified new pair with no label is `unassessed` and exported to `pending_review.jsonl`; the evaluator never invents a label or calls an evaluation LLM.
- Only IDs actually selected for the rendered recommendations are scored, not all accepted judgments or the four-problem internal context. Repeats count once within a question, and again on separate questions.
- **Assessed precision** is relevant / (relevant + unrelated), where relevant includes direct, related and stretch labels. Uncertain, unassessed and mapping-unscored counts stay visible. **Label coverage** is labeled / all returned recommendations and includes reviewed uncertain labels. Precision bounds use all returned items and allow unresolved items to be relevant; they are not confidence intervals.
- **Hit rate** is completed ordinary questions with at least one relevant recommendation / completed ordinary questions. Failed executions have no inferred score and are excluded from completed-question denominators, with attempted counts and failures recorded separately. Failures are not abstentions. Abstention rate and naming-control conformance remain supporting diagnostics.
- **Annotated-target recall (micro)** is original positive targets recommended / original positive targets, summed across completed ordinary questions with targets. Targets count once per question and again across wordings. Questions with invalid recommendation mappings or unscored recommendation-stage coverage are excluded and counted explicitly. No-target questions have no recall denominator. The targets are incomplete; this is not exhaustive semantic recall or document-QA evidence-text recall. Existing JSON/CSV field names and scoring labels are retained for compatibility; the summary uses these metric names.
- Original positive targets drive secondary overlap diagnostics at merged candidates, shortlist, final context and final recommendation stages. A chunk must overlap that problem's body on the correct source/page; sharing a page is insufficient. A small overlap need not explain the problem, and the targets do not exhaust suitable evidence or exercises.
- Each recommendation's identity, technical chunk, selected quotes and offsets are checked against original PDFs. Mapping failures remain unscored, not silently omitted. Literal occurrence does not establish semantic entailment or score explanation correctness.

Reference hashes, identities and quotes are verified before inference. Labeled pages are compared with loaded corpus pages to detect stale artifacts. The original PDFs, corpus/data hashes and index fingerprints identify each experiment.

## Runs and recovery

Configuration and output paths live under `leetcode_recommendation_evaluation`. Azure defaults to two isolated pipelines; local Qwen is sequential. Build mode indexes the whole corpus once; other workers load those artifacts. Both scripts retain their original production algorithms.

Checkpoints are atomic per-question JSON files under the ignored results `.checkpoint/` directory. `--resume` requires the same selected question IDs, code, data, configuration and index bytes. Only indexing mode may change: resume always loads existing verified artifacts, never rebuilds. Completed and failed question records are preserved; unsaved in-flight work may have incurred charges and must be repeated. `--restart` explicitly starts a new run. A fresh command refuses an unfinished checkpoint; an already completed run can be replaced. A completed checkpoint can regenerate reports without loading a model or making calls.

The imported published baseline has no live checkpoint; `--resume` applies to runs started by the new evaluator. Checkpoint ownership uses a POSIX file lock (Linux/macOS). Historical diagnostics remain local archives and may reference the pre-reorganization layout; the published workflow does not import them.

Reports include actual settings/concurrency, source/index/code/data fingerprints, timings, call counts, candidate-validation failures and available Azure token usage. Recorded usage excludes unobserved interrupted calls or SDK retries and is not the Azure bill. Credentials and bulk API traces are not published.

Question IDs remain stable. Changes to questions, reference meaning or source bytes require a documented benchmark-version update and updated hashes. The included results preserve the historical GPT-5.1 inference/configuration and timing provenance; they are not evidence of a fresh run or a pure model-size effect.

This directory preserves the v1.0/v1.1 references and manifests; current configuration selects the separate v2 dataset. Checkpoint fingerprints from another version are incompatible. Preserve the old configuration/reference version when reproducing an experiment, or explicitly start a new run. Historical published v1 reports are unchanged and describe the 180-pair version; expansion alone does not create new evaluation results.
