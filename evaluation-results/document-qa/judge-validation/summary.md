# QA judge performance

The latest Azure OpenAI `gpt-5.1` judge was evaluated on 48 distinct cases in 2 runs. Exact agreement requires all expected labels and the claim inventory to match. Unscored judgments remain in the denominator.

| Run | Exact case agreement | Valid judgments | Unscored |
|---|---:|---:|---:|
| 1 | 47/48 (97.9%) | 48/48 | 0 |
| 2 | 46/48 (95.8%) | 47/48 | 1 |

**Combined agreement: 93/96 (96.9%).** Repeated judgments are not additional distinct cases.

## Case composition

The benchmark includes 30 development cases that informed judge improvements and 18 reserved cases not used to refine this judge. The combined score mixes these groups and does not establish independent test accuracy. Expected labels are automatically source-audited, not human-approved. There is no pass/fail qualification threshold.

| Group | Run 1 | Run 2 |
|---|---:|---:|
| Development | 30/30 (100.0%) | 30/30 (100.0%) |
| Reserved | 17/18 (94.4%) | 16/18 (88.9%) |

## Tasks

| Task | Run 1 | Run 2 |
|---|---:|---:|
| Coverage | 15/16 (93.8%) | 16/16 (100.0%) |
| Grounding | 22/22 (100.0%) | 21/22 (95.5%) |
| Abstention | 10/10 (100.0%) | 9/10 (90.0%) |

## Consistency

Usable and identical label/inventory decisions on 45/48 repeated pairs (93.8%). Among pairs with two valid judgments, agreement was 45/47 (95.7%). Consistency alone does not establish correctness.

## Errors and unscored judgments

| Case | Run | Expected labels | Observed labels | Status |
|---|---:|---|---|---|
| judge-v2-005 | 1 | `contradicted` | `covered` | `valid` |
| judge-v2-008 | 2 | `supported` | `<unscored>` | `unscored` |
| judge-v2-016 | 2 | `mixed` | `unsupported_answer` | `valid` |

All judgments, reasons, source/context quotes, exclusions, confusion counts, and per-label precision/recall/F1 are in [details.json](details.json). [per_case.csv](per_case.csv) contains one row per case/run. [Dataset and evidence](../../../evaluation-data/qa-judge-validation/README.md).

## Provenance

- Reporting mode: `offline_consolidation_of_latest_judgments`. Saved judgments were not relabeled during consolidation.
- Returned model IDs: `['gpt-5.1-2025-11-13']`.
- Dataset SHA-256: `160deb16bdf9d5430834aa5a9b8519ab5d0d18d78df4e6050d52e17338709b83`.
- Judge protocol SHA-256: `69169d5711d94b69514aa0b0d98eba54713ff5a99d8a383116135e9830ed450d`.
- Source verification: `{'source_anchors_verified': 41, 'pdf_pages_read': 32, 'pdf_hashes_verified': 6}`.
- Recorded calls for these judgments: 132. Recorded tokens: `{'prompt_tokens': 81795, 'completion_tokens': 15509, 'total_tokens': 97304}`. SDK retries may add requests. Usage is not a bill.

These are judge-validation results, not RAG answer-quality or retrieval scores. Literal quote checks establish provenance, not semantic entailment. Unmatched or ambiguous claim mappings count as inventory errors. No-claim controls affect case agreement but are not a semantic class in macro F1.
