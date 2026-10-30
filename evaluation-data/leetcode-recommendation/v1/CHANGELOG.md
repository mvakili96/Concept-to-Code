# LeetCode benchmark change log

## 1.1.0 — 2026-10-26

- Preserved all 40 questions, stable IDs, source restrictions, technical evidence and original positive recall targets.
- Preserved all 180 v1.0 pair records and both v1.0 reference/manifest files.
- Scanned all 4,000 statements with fixed BM25 and character-TF-IDF queries plus seeded sampling, without using saved recommendations. Collected 99 pairs: 27 inherited and 72 new.
- Source-audited 72 added pairs: 2 direct, 15 related, 13 stretch, 39 unrelated, 3 uncertain. Total labels: 252; uncertain: 8. No extraction/identity quarantines.
- Added exact source prose, passage offsets, rationales, limitations, reviewer provenance, discovery ranks, reproducible collection assets and a readable annotation audit.
- Rechecked the two explicit-naming controls against every statement; no required literal matched.
- Switched the configured references/manifest to v1.1. Kept historical evaluation files byte-for-byte unchanged; no inference or performance rerun.

## 1.0.0 — historical baseline

- Published the 40-question pool: 20 topics, 36 ordinary questions and four naming controls.
- Preserved 173 broader-rubric pooled judgments and seven earlier source-verified positives.
- Stored 180 topic/problem pairs; five labels remained uncertain. The pool was derived from previous diagnostic outputs and selected targets, not an exhaustive relevance audit of every problem.
