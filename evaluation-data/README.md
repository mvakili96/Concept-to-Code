# Evaluation benchmarks

The repository has two source-grounded benchmarks for comparing pipeline changes and ablations. Both evaluators call the production pipeline in `main.py`. They score its output against saved references, without asking an evaluation LLM to grade it.

| Benchmark | Questions | Reference unit | Evaluated output |
|---|---|---|---|
| [Document QA](document-qa/) | 50, including 47 answerable and three controlled unanswerable questions | Specific PDF passages linked to an answer's required facts | Final reranked context supplied to the answering LLM |
| [LeetCode v2](leetcode-recommendation/v2/) | 40, covering 20 topics with two wordings each | Source-audited relevance labels for topic/problem pairs | Problems actually recommended to the user |

See [METRICS.md](METRICS.md) for formulas, denominators, relevance labels, and worked examples. LeetCode reports macro **Capped Recall@k**, with `k` taken from the configured recommendation limit. Full annotated-target recall remains a secondary coverage diagnostic. The two benchmarks use different units, so their precision and recall percentages are not directly comparable.

## Document QA: what one sample contains

[`document-qa/rag_benchmark_v1.jsonl`](document-qa/rag_benchmark_v1.jsonl) has one JSON object per question. Despite the filename, its current benchmark version is `1.2.0` and its schema version is `1.1.0`.

| Fields | Purpose |
|---|---|
| `id`, `question`, `primary_category`, `tags`, `difficulty` | Stable identity, natural query, and coverage labels |
| `allowed_sources`, `answerability` | Admissible PDF filenames, whether the answer exists within them, and expected answering or abstention behavior |
| `reference_answer`, `atomic_required_facts` | A supported reference answer split into individual claims, with links to evidence IDs |
| `evidence_records` | Exact supporting quotes, filenames, one-based physical `pdf_page` numbers, optional printed page labels, and fact links |
| `required_evidence_groups` | Which evidence groups are jointly required and which passages can alternatively support the same fact |
| `terminology_variants`, `verified_distractor_passages` | Source-supported wording examples and optional plausible but insufficient passages |
| `unanswerable_audit`, review and eligibility fields, `corpus_manifest` | Allowed-source checks, verification provenance, evaluation eligibility, and corpus identity |

For example, **`ragbench-v1-001`** asks how Hough voting works and what orientation-aware alternative the book suggests. Its reference answer has two atomic facts, both linked to an exact passage from *Computer Vision: Algorithms and Applications.pdf*, physical page **504**. These are source passages, not fixed retrieval chunks. Changing chunk size does not change the reference IDs.

The three unanswerable cases restrict the question to a source that does not provide the requested fact. Their records contain an absence audit and expected abstention. A failed retrieval search is not used as proof of unanswerability.

The dataset contains 125 atomic facts, 76 evidence records, and ten distractor passages. Facts and evidence groups support inspection, but the current evaluator scores text overlap rather than semantic fact or group satisfaction. [Schema](document-qa/SCHEMA.md) · [All questions, answers, and quotes](document-qa/REVIEW.md) · [Coverage](document-qa/COVERAGE.md).

## LeetCode v2: what one sample contains

[`leetcode-recommendation/v2/leetcode_benchmark_v2.jsonl`](leetcode-recommendation/v2/leetcode_benchmark_v2.jsonl) contains question records. Shared evidence and labels are stored separately in [`references_v2.json`](leetcode-recommendation/v2/references_v2.json), so the two wordings of a topic do not duplicate its annotations.

| Record | Contents |
|---|---|
| Question | `id`, `topic_id`, `question`, `wording` (`short` or `descriptive`), `kind`, `allowed_technical_sources`, expected behavior, difficulty, and tags |
| Shared topic, looked up by `topic_id` | Technical mechanism, exact textbook evidence, source restrictions, optional literal-naming condition, positive `target_problem_numbers`, and corpus-screening provenance |
| Topic/problem pair, keyed as `topic_id::lcNUMBER` | Verified problem number, title, difficulty, source/page/body bounds, exact problem evidence, linked technical evidence, relevance label, rationale, limitation, and review provenance |

For example, **`lcrec-v2-001-short`** asks for Dijkstra contour-tracing practice. Both wordings share topic `lcrec-v2-001`, whose technical evidence is on physical CV pages **499–500**. Pair **`lcrec-v2-001::lc1091`** labels *Shortest Path in Binary Matrix* a direct match and cites its statement on physical LeetCode PDF page **546**. Its limitation explains that sharing a shortest-path objective does not require the same Dijkstra implementation.

There are 36 ordinary requests and four literal-naming controls. The controls require a statement that explicitly names a specified method. Abstaining on those controls does not claim that no broader related practice exists.

The 360 annotated pairs include **21 direct matches, 180 related-practice connections, 134 stretch connections, 15 unrelated pairs, and ten uncertain pairs**. All **335 positive pairs** are recall targets in v2. The three positive categories can be read as **Match, Relevant, and Stretch**. Their exact stored names and metric treatment are explained in [METRICS.md](METRICS.md#leetcode-relevance-labels).

The catalogue covers all 4,000 original statements. The scan ledger records 80,000 topic/statement text-screening decisions across 20 topics. This is not 80,000 individual semantic relevance judgments. Unlisted pairs remain unassessed. [Schema](leetcode-recommendation/v2/SCHEMA.md) · [Readable annotations](leetcode-recommendation/v2/REVIEW.md) · [Screening and coverage limitations](leetcode-recommendation/v2/COVERAGE.md).

## Versions, source anchors, and review status

- The original LeetCode [v1 benchmark](leetcode-recommendation/v1/) and its reports remain historical. Its explicit recall-target subset differs from v2's all-positive target policy.
- Corpus manifests pin PDF bytes with SHA-256 hashes. PDF files belong in the ignored `documents/` directory. Pages are one-based physical PDF pages, not printed book labels. LeetCode passage offsets are zero-based `[start, end_exclusive)` character ranges.
- Evidence is anchored to original prose and problem identities, not current chunk IDs. Figures, captions, tables, layout interpretation, and scanned content are excluded from the reference evidence.
- `reviewed_and_verified`, `source_audited`, and `codex_source_audit` describe automated source auditing. They do not mean human approval or guarantee semantic correctness.
- These are fixed development benchmarks with stable question IDs, not held-out train/test splits. Two wordings of one topic are not two independent topics. Current results support development comparisons rather than held-out generalization.

## Run and inspect results

Use `python evaluate_document_qa.py` or `python evaluate_leetcode_recommendation.py` from the repository root. Dataset and output paths are configured in `config.yml`. Both scripts accept `--limit 1` for a first-question check. LeetCode also supports `--resume` for compatible saved progress and `--restart` for a fresh run. Azure-backed inference incurs API usage.

[Document-QA report](../evaluation-results/document-qa/summary.md) · [Latest LeetCode collective report](../evaluation-results/leetcode-recommendation/v2/experiments/title-selection-full-source-fixed/source_fix.md) · [All results](../evaluation-results/README.md).

The latest LeetCode report combines saved results with targeted reruns. Its provenance records the execution segments rather than claiming a fresh homogeneous full-benchmark run. Capped recall was added to saved reports offline, preserving their inference records and settings. Versioned manifests and frozen preparation documents retain their original contents.
