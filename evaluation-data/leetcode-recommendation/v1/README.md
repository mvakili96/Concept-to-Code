# LeetCode recommendation benchmark

One fixed benchmark: **40 questions, 20 topics, 36 ordinary requests and four explicit-naming controls**. Short/descriptive variants retain stable IDs; neither group is held out.

A separate [fresh-topic v2 dataset](../v2/README.md) adds 40 questions on 20 new primary topics, full-statement corpus screening, and source-audited references. Current configuration selects v2; this directory preserves the earlier benchmark and both historical reference versions.

- `leetcode_benchmark_v1.jsonl`: one question per line, wording, kind and source restrictions.
- `references_v1_1.json`: shared technical evidence and **252** source-audited topic/problem pairs with quotes, physical pages, offsets, relevance rationales and limitations. Eight relationships remain explicitly uncertain.
- `corpus_manifest_v1_1.json`: current source/data hashes, page counts and annotation-artifact hashes.
- `references_v1.json` and `corpus_manifest_v1.json`: unchanged **180-pair** historical reference version used by the published GPT-5.1 report.
- [COLLECTION.md](COLLECTION.md): how annotations were collected, their bias and coverage limits, and offline reproduction.
- [ANNOTATION_REVIEW_v1_1.md](ANNOTATION_REVIEW_v1_1.md): all 72 added decisions beside original problem prose and technical evidence.
- [CHANGELOG.md](CHANGELOG.md): version history; question text, IDs and original recall targets remain unchanged.
- [SCHEMA.md](SCHEMA.md): scoring rules, reference scope and provenance.

Run `python evaluate_leetcode_recommendation.py` from the repo root, or add `--limit 1`. Only final recommended problems are scored. Labels are incomplete: new pairs are unassessed, not automatically wrong; uncertain pairs remain visible. Useful includes explicitly limited stretch practice, not just implementations of the named method. Quotes establish provenance, not guaranteed explanation correctness. PDFs and persisted indexes are not distributed.

The original labels were pooled from previous system outputs and selected targets. The v1.1 addition independently collects candidates from all 4,000 statements using fixed topic-operation queries, BM25, character TF-IDF and seeded random sampling, then audits the added candidates. This improves coverage; it does not assess every possible pair or establish independent held-out ground truth. No human approval is claimed. Saved v1 reports remain historical v1.0 results and have not been replaced or rerun.
