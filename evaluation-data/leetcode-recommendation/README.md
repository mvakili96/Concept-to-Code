# LeetCode recommendation benchmarks

- [v1/](v1/): the original 40-question development benchmark, historical 180-pair references and the 252-pair annotation expansion. [Saved baseline](../../evaluation-results/leetcode-recommendation/v1/summary.md).
- [v2/](v2/): 40 questions on 20 new primary topics, complete text screening of all 4,000 statements per topic, and 360 source-audited relationships. [Latest collective results](../../evaluation-results/leetcode-recommendation/v2/experiments/title-selection-full-source-fixed/source_fix.md).

Configuration selects v2. Both versions use the same production evaluator. Source-audited references remain interpretive and incomplete. Unlisted pairs are unassessed. The v1 report retains its historical paths/settings as provenance.

## Samples, labels, and metrics

A question record points to shared textbook evidence and topic/problem reference pairs through `topic_id`. The short and descriptive wordings share annotations but are evaluated independently. See the [benchmark guide](../README.md#leetcode-v2-what-one-sample-contains) for an actual example and field descriptions.

The three positive grades are **Match** (`direct_match`), **Relevant** (`related_practice`), and **Stretch** (`stretch_connection`). All count as useful for assessed precision and hit rate. In v2, all 335 positive pairs also belong to the recall target sets. Unrelated and uncertain reference labels are separate, and an unlisted pair remains unassessed.

[METRICS.md](../METRICS.md) documents the exact calculations, exclusions, aggregation, prediction scenarios, and the output-cap explanation for low recall. Recall is not restricted to direct matches. Versioned v1/v2 documents and manifests retain their frozen contents.

Preparation and freeze files retain creation-time paths, configuration fingerprints and not-yet-evaluated status. Current execution settings and completion status belong to the versioned evaluation reports, rather than rewriting those historical records.
