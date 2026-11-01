# QA judge benchmark

**48 source-audited cases**, evaluated twice with the latest Azure OpenAI GPT-5.1 judge. This benchmark evaluates the answer evaluator itself. No retrieval, reranking, or answer generation is run.

| Cases | Purpose |
|---|---|
| 30 development | Informed improvements to the judge, including four known regression cases |
| 18 reserved | Kept separate from judge refinement |

The combined score includes both groups and does not establish independent test accuracy. Expected labels are automatically source-audited, not human-approved. Existing question IDs, prepared answers, expected labels, and PDF evidence are preserved.

[Performance report](../../evaluation-results/document-qa/judge-validation/summary.md) · [Readable questions, answers, labels, and evidence](REVIEW.md)

## Contents and schema

`cases.jsonl` contains one record per case, using schema version `1.1.0`:

| Fields | Meaning |
|---|---|
| `id`, `stage`, `partition`, `tags` | Stable identity, coverage/grounding/abstention task, and development/reserved group |
| `question`, `generated_answer` | Question and prepared answer supplied to the judge |
| `reference_answer`, `required_facts` | Reference-based coverage inputs, or the expected insufficiency for abstention |
| `retrieved_context` | Grounding input, without reference facts or expected labels |
| `expected_labels`, `expected_rationale` | Source-audited expected judgments, excluded from API inputs |
| `expected_claims` | Expected factual excerpts with IDs and original-answer character offsets |
| `source_anchor_ids` | Links to exact PDF prose in the manifest |
| Review/provenance fields | Automated audit method and explicit absence of human approval |

`manifest.json` pins dataset bytes, the original corpus manifest, and PDF prose anchors with SHA-256 hashes. Anchors include filenames, one-based physical PDF pages, exact quotes, and zero-based `[start, end_exclusive)` character offsets. They survive chunk-size changes. The manifest preserves collection provenance without duplicating the datasets.

There are 16 coverage, 22 grounding, and 10 abstention cases. Some contain multiple facts or claims. Cases cover paraphrases, numerical and unit changes, omitted conditions, neighboring technical terms, unsupported assertions, mixed guesses and abstention, and citation-only output. Formatting controls follow explicit inventory rules and need no new factual claim about a PDF. Grounding concerns only the supplied context, and closed-excerpt abstention cases make no claim that a fact is absent from an entire book.

## Run

```bash
python evaluate_qa_judge.py --verify-only
python evaluate_qa_judge.py
```

`--verify-only` checks all PDF hashes, source pages/quotes/offsets, dataset integrity, and expected-claim offsets without API calls. The default evaluation runs all 48 cases twice. `--limit 1` selects a subset. `--resume` reuses compatible saved judgments, including failures. `--restart` starts a fresh evaluation. Runtime checkpoints are local and ignored.

## Scoring

**Exact case agreement = fully matching cases / all attempted cases.** Every required label and the expected claim inventory must agree. Unscored, uncertain, missing, extra, or ambiguously aligned judgments receive no exact-case credit.

Reports show both runs and their combined aggregate, retaining the development/reserved breakdown. They also record task-specific confusion counts, per-label precision/recall/F1, and repeated-decision agreement. Repetition does not double the number of independent examples. A judge can consistently repeat a mistake. There is no pass/fail qualification threshold.

The saved results contain only the latest judge: **47/48 (97.9%)** in run 1 and **46/48 (95.8%)** in run 2, totaling **93/96 judgments (96.9%)**. Three unsuccessful judgments remain visible, including one unscored quote-validation failure. This is a small automatically audited benchmark, with topics from the same PDF library. It does not establish human-level accuracy. Future tuning using the reserved cases makes them development examples as well.
