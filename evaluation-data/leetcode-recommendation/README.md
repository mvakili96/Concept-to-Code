# LeetCode recommendation benchmark

One fixed benchmark: **40 questions, 20 topics, 36 ordinary requests and four explicit-naming controls**. Short/descriptive variants retain stable IDs; neither group is held out.

- `leetcode_benchmark_v1.jsonl`: one question per line, wording, kind and source restrictions.
- `references_v1.json`: shared technical evidence and **180** reviewed topic/problem pairs with quotes, physical pages, offsets, relevance rationales and limitations.
- `corpus_manifest_v1.json`: source/data hashes, page counts and version.
- [SCHEMA.md](SCHEMA.md): scoring rules, reference scope and provenance.

Run `python evaluate_leetcode_recommendation.py` from the repo root, or add `--limit 1`. Only final recommended problems are scored. Labels are incomplete: new pairs are unassessed, not automatically wrong; uncertain pairs remain visible. Useful includes explicitly limited stretch practice, not just implementations of the named method. Quotes establish provenance, not guaranteed explanation correctness. PDFs and persisted indexes are not distributed.
