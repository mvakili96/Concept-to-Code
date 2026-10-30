# Annotation collection and limits

## Historical v1.0 pool

The 180 original topic/problem labels were collected from prior diagnostic outputs and selected positive reference targets. The collection preserved 173 broader-rubric judgments and seven earlier positives. A source audit checked the corresponding PDF passages and problem identities. It did not individually judge every one of the 4,000 problems for every topic. In particular, linear filtering's original eight labels were a collected pool, not all relevant problems in the PDF.

The published GPT-5.1 report used these annotations. Candidate collection partly depended on systems being evaluated, and the topics had already been inspected during development. High assessed precision and full observed label coverage therefore do not imply independent, exhaustive or human-approved ground truth. The v1.0 files and historical reports are unchanged.

## Output-independent v1.1 expansion

Before collecting new candidates, `collection_plan_v1_1.json` fixed one search query for each of the 18 ordinary topics. Queries describe operations in the existing technical evidence, rather than known LeetCode identities. The two explicit-naming control topics use a separate all-statement literal scan.

`collect_candidates.py` extracts all **4,000 unique source-owned problem statements** directly from the original PDF using the recorded heading/footer rules. It verifies every original corpus PDF's hash. It does not load persisted indexes, production prompts, saved predictions, diagnostic results or model-judge explanations, and makes no API calls.

Candidate methods are:

1. **BM25:** word-token scores over each title and statement prose, excluding the constraints section.
2. **Character TF-IDF cosine:** four-character substrings of normalized statement/title tokens. IDF is `log((1+4000)/(1+document_frequency))+1`; term frequency is the raw count. Document and query vectors are L2-normalized. This provides spelling-fragment overlap, not semantic embeddings.
3. **Seeded sampling:** one random remaining problem per ordinary topic, with seed `20261026`. Sampling alone never establishes that an example is negative.

Each ranked method contributes its first three results, with problem number breaking tied scores. Results are deduplicated per topic while retaining all contributing methods and ranks. This produces **99 pairs: 27 already labeled and 72 new**. All 72 additions were read alongside their topic's original technical prose and assigned an individual rationale and limitation. Quotes, physical pages, offsets, identities and evidence links were then checked by independently re-extracting the original PDFs. The three SQL-related distractors use only the prose task description; their labels do not require interpreting schema tables.

Added labels: **2 direct, 15 related, 13 stretch, 39 unrelated and 3 uncertain**. The uncertain cases remain excluded from assessed precision. All 72 passed source/identity checks; none required quarantine for unverifiable extraction. The same coding assistant performed the semantic review and had prior exposure to the project. This is output-independent collection, not a blinded or independently adjudicated study. Review method is `codex_source_audit`; the exact serving model identifier is unavailable. Human-reviewed status remains false.

Both naming-control phrases were absent from all 4,000 normalized titles/bodies. This verifies only the explicit phrase requirement: `fundamental matrix` and `n-gram language model`. It does not establish that related geometry or text-processing exercises are absent. Matching is a normalized literal substring scan, not a semantic search or synonym check.

## Versioning and reproducibility

The current reference set contains **252 pairs**: all 180 old records, unchanged, plus 72 additions. All 40 questions, IDs, source restrictions, topic evidence and original positive target lists are unchanged. In particular, added positive labels do not enlarge the original annotated-target recall denominator. Eight relationships are uncertain in total: five inherited and three new.

With the supplied PDFs and installed project dependencies, reproduce candidate collection offline from the repo root:

```bash
python evaluation-data/leetcode-recommendation/v1/collect_candidates.py --output-dir /tmp/leetcode-annotation-pool
```

Use an unused output directory. Compare the generated `candidate_pool_v1_1.jsonl` with the committed pool. The collector only produces candidate identities, ranks and source bounds; it never generates relevance labels. The plan, collector, dependencies, PDF and pool fingerprints are recorded in the collection manifest; the corpus manifest pins the curated references. `ANNOTATION_REVIEW_v1_1.md` displays the added decisions with exact source evidence.

Moving the collector into `v1/` changed its repository-root path calculation. The corpus manifest records that layout migration and updated artifact hash; the old collection manifest retains the original code hash as historical provenance. The candidate pool, questions and relevance labels are unchanged.

To reproduce v1.1, explicitly select this directory's `references_v1_1.json`, `corpus_manifest_v1_1.json` and question file. Current configuration selects the separate v2 dataset. Historical v1.0 results remain byte-for-byte unchanged and retain their original settings/fingerprints. A new run against different references is a different benchmark version; incompatible old checkpoints must not be resumed.

## Remaining limits

- Only the collected pairs were semantically audited. Scoring all 4,000 candidates during collection is not the same as labeling 4,000 relationships per topic.
- The top-three lexical pools are deliberately manageable and can miss conceptual alternatives; both methods share lexical bias. One random example per topic does not estimate the prevalence of unrelated problems.
- Added labels are post-hoc development annotations. They do not create a held-out set, resolve the inherited uncertain cases, or remove prior system-output bias from the inherited pool.
- Relevant means useful practice transfer under the direct/related/stretch rubric. Matching vocabulary alone is insufficient, and no solution algorithm is inferred merely because it could solve the problem.
- Exact quote checks establish provenance, not semantic correctness. Automated reviewer judgments can be wrong; there was no independent assessor or human approval.
- Assessed precision excludes unassessed/uncertain pairs; report label coverage with it. Hit rate measures at least one assessed relevant suggestion. Original-target recall remains a secondary, incomplete-target diagnostic.
