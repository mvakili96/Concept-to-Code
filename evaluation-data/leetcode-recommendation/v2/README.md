# Fresh-topic LeetCode benchmark v2

**40 questions, 20 new primary topics, 36 ordinary requests and four explicit-naming controls.** Each topic has short and descriptive wordings. This uses the lower end of the requested 40–50 range to retain clear prose grounding. No production evaluation or paid API calls were run to create it.

- `leetcode_benchmark_v2.jsonl`: fixed questions, IDs, source restrictions, difficulty and tags.
- `references_v2.json`: technical evidence and **360** source-audited topic/problem judgments: 21 direct, 180 related, 134 stretch, 15 unrelated and 10 uncertain.
- `problem_catalogue_v2.jsonl`: all 4,000 source-owned problem identities, physical pages, body bounds and hashes; no current chunk IDs.
- `scan_ledger_v2.jsonl`: 800 reproducible batches of 100 statements—4,000 statements for every topic, shared across its two wordings.
- `question_freeze_v2.json`, `NOVELTY_AUDIT_v2.json`: question/mechanism definitions, code fingerprints, prior-topic exclusions and novelty rationales.
- `corpus_manifest_v2.json`: source/data/preparation fingerprints.
- [REVIEW.md](REVIEW.md): every question and annotated relationship beside exact source prose and physical page references.
- [SCHEMA.md](SCHEMA.md), [COVERAGE.md](COVERAGE.md): format, collection scope and remaining limitations.

Topics were checked against the old LeetCode cases, document-QA questions, production prompt examples and known conversation smoke tests. Existing topics such as linear filtering, Hough transforms, replication and data warehousing are excluded. The novelty claim concerns new **primary topics**: general primitives and LeetCode identities can recur. No new production outputs were used to choose or label these questions. No formal train/test split is introduced.

The full original statement text was normalized and screened for every topic using explicit operation/terminology patterns, without a top-k cutoff. Additional catalogue review supplied source-backed matches outside those patterns. Each published pair was individually checked against original task prose and technical evidence. Both naming-control phrases were absent from every original statement.

**Important scope:** all-corpus screening is complete; a semantic relevance judgment for every topic/problem combination is not claimed. The ledger distinguishes scanned statements from individually audited pairs. Pattern misses remain possible, so an unlisted pair stays **unassessed**, never automatically unrelated. These references support assessed precision and annotated-positive recall; they do not establish exhaustive semantic recall. This limitation is explicit rather than hidden behind a scan count.

The original recall-target subset is not reused: **all 335 positively annotated pairs** are targets for their topics. With at most three recommendations, recall can still be small when a topic has many relevant targets. See the coverage report for the achievable ceiling.

Verify sources and reproduce the full-statement scan offline:

```bash
python evaluation-data/leetcode-recommendation/v2/verify_dataset.py
```

The verifier reads original PDFs and benchmark data; it does not load the production models, call an API, evaluate recommendations, or overwrite reports. Review is automated source auditing, not human approval or guaranteed semantic correctness.

Earlier data and published results are preserved under `v1/`. Configuration now selects these v2 paths under `leetcode_recommendation_evaluation` and uses a separate output directory:

```yaml
dataset_path: evaluation-data/leetcode-recommendation/v2/leetcode_benchmark_v2.jsonl
references_path: evaluation-data/leetcode-recommendation/v2/references_v2.json
manifest_path: evaluation-data/leetcode-recommendation/v2/corpus_manifest_v2.json
results_dir: evaluation-results/leetcode-recommendation/v2
```

V2 results are published separately under `evaluation-results/leetcode-recommendation/v2/` when evaluation completes. Do not reuse an old checkpoint. Once these topics are used to tune prompts or retrieval, describe subsequent results as development-benchmark comparisons, not an untouched first evaluation. Novelty relative to available project history does not establish absence from model pretraining or unrecorded past work.
