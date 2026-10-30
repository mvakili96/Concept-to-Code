# Coverage and limitations

**40 questions / 20 topic clusters:** 36 ordinary requests and four naming controls. Each topic has two wordings; the 40 observations are not 40 independent topics.

| Topic | Source | Full statements screened | Pattern matches | Positive / unrelated / uncertain references |
|---|---|---:|---:|---:|
| lcrec-v2-001: Intelligent-scissors minimum-cost paths | Computer Vision: Algorithms and Applications.pdf | 4,000 | 76 | 63 / 1 / 0 |
| lcrec-v2-002: Graph-cut energy minimization | Computer Vision: Algorithms and Applications.pdf | 4,000 | 61 | 5 / 1 / 3 |
| lcrec-v2-003: Histogram equalization | Computer Vision: Algorithms and Applications.pdf | 4,000 | 18 | 15 / 1 / 0 |
| lcrec-v2-004: Frequency-sensitive lossless code assignment | Probabilistic Machine Learning.pdf | 4,000 | 52 | 5 / 1 / 0 |
| lcrec-v2-005: Maximum-weight bipartite data association | Probabilistic Machine Learning.pdf | 4,000 | 131 | 9 / 1 / 3 |
| lcrec-v2-006: Inverse-CDF random sampling | Probabilistic Machine Learning.pdf | 4,000 | 52 | 10 / 1 / 0 |
| lcrec-v2-007: Round-robin request dispatch | Grokking-the-system-design-interview-free.pdf | 4,000 | 112 | 10 / 1 / 0 |
| lcrec-v2-008: Capacity-driven quadtree subdivision | Grokking-the-system-design-interview-free.pdf | 4,000 | 2 | 2 / 1 / 0 |
| lcrec-v2-009: Continuation-bit variable-length integers | Designing Data-Intensive Applications.pdf | 4,000 | 11 | 4 / 1 / 0 |
| lcrec-v2-010: Broadcast hash joins | Designing Data-Intensive Applications.pdf | 4,000 | 63 | 11 / 1 / 0 |
| lcrec-v2-011: Keyed grouping and aggregation | Designing Data-Intensive Applications.pdf | 4,000 | 743 | 71 / 1 / 0 |
| lcrec-v2-012: Bitmap predicate intersection | Designing Data-Intensive Applications.pdf | 4,000 | 52 | 38 / 1 / 0 |
| lcrec-v2-013: CKY chart recognition | Speech and Language Processing.pdf | 4,000 | 120 | 31 / 0 / 1 |
| lcrec-v2-014: Maximum-spanning-tree dependency parsing | Speech and Language Processing.pdf | 4,000 | 61 | 7 / 1 / 0 |
| lcrec-v2-015: Shift-reduce dependency parsing | Speech and Language Processing.pdf | 4,000 | 121 | 38 / 0 / 1 |
| lcrec-v2-016: B-tree page splitting | Designing Data-Intensive Applications.pdf | 4,000 | 38 | 5 / 1 / 0 |
| lcrec-v2-017: Bounded-buffer backpressure | Designing Data-Intensive Applications.pdf | 4,000 | 10 | 3 / 1 / 1 |
| lcrec-v2-018: K-means centroid updates | Speech and Language Processing.pdf | 4,000 | 38 | 8 / 0 / 1 |
| lcrec-v2-019: Explicit Sinkhorn naming control | Probabilistic Machine Learning.pdf | 4,000 | 0 | 0 / 0 / 0 |
| lcrec-v2-020: Explicit coreference naming control | Speech and Language Processing.pdf | 4,000 | 0 | 0 / 0 / 0 |

Across topics: 335 positively annotated pairs, 15 explicit negatives and 10 uncertain pairs. Screening covers 80,000 topic/statement combinations. The 360 published pair judgments are a separate count; most combinations have no individual semantic label.

At a recommendation cap of three, the largest possible micro recall against these annotated positives is 53/335 = 15.8%. Each topic appears twice, so the question-level numerator/denominator double without changing that ratio. This ceiling is independent of model performance and is not a measured result.

## What was checked

- All six original PDF hashes and all 4,000 source-owned problem identities/body hashes.
- Exact reference quotes, physical pages, character offsets, technical-source restrictions and evidence links.
- All 40 contiguous 100-statement ranges per topic; no top-k selection gate.
- All positive annotations are recall targets; uncertain examples remain explicitly uncertain.
- Naming-control phrases are absent from all normalized original titles/bodies.
- New primary topics were checked against prior benchmarks, documented diagnostics, prompt examples and known smoke-test topics; code and questions are fingerprinted.

## Remaining limitations

- Full-text pattern screening does not prove semantic exhaustiveness. Each retained relationship was source-audited, but the other combinations are not automatically negative. Conceptual alternatives can be missed; unlisted outputs remain unassessed.
- Related and stretch annotations are interpretive. Shared concrete primitives can support useful practice without implementing the source method. Automated review is not human approval or independent adjudication.
- The chosen topics are new relative to checked project history. Public LeetCode problem identities, basic operations and broad subject areas can overlap old work. Unknown private history and model pretraining exposure cannot be ruled out.
- Two wordings share annotations and a topic; do not treat them as independent topic coverage or tune on one and call the other held out.
- Dataset preparation did not run production inference. Performance is reported separately in the versioned results directory; disclose later use of these questions for development.
- Figures, captions, tables and scanned content do not support the retained evidence. SQL-related annotations use the extracted prose task rather than interpreting schema/example tables.
