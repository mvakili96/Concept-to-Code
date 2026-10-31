# LeetCode recommendation benchmarks

- [v1/](v1/): the original 40-question development benchmark, historical 180-pair references and the 252-pair annotation expansion.
- [v2/](v2/): 40 questions on 20 new primary topics, complete text screening of all 4,000 statements per topic, and 360 source-audited relationships. [Final title-selection results](../../evaluation-results/leetcode-recommendation/v2/summary.md).

Configuration selects v2. Both versions use the same production evaluator. Source-audited references remain interpretive and incomplete. Unlisted pairs are unassessed. Only the final v2 title-selection result is published.

## Samples, labels, and metrics

A question record points to shared textbook evidence and topic/problem reference pairs through `topic_id`. The short and descriptive wordings share annotations but are evaluated independently. See the [benchmark guide](../README.md#leetcode-v2-what-one-sample-contains) for an actual example and field descriptions.

The three positive grades are **Match** (`direct_match`), **Relevant** (`related_practice`), and **Stretch** (`stretch_connection`). All count as useful for assessed precision and hit rate. In v2, all 335 positive pairs also belong to the recall target sets. Unrelated and uncertain reference labels are separate, and an unlisted pair remains unassessed.

[METRICS.md](../METRICS.md) documents the exact calculations, exclusions, aggregation, and prediction scenarios. The headline recall is macro **Capped Recall@k**, dividing target hits in the top `k` returns by `min(k, positive target count)` per question. `k` is the run's configured recommendation limit. Full annotated-target recall remains secondary. All three positive grades count when included in the version's target set. Versioned v1/v2 documents and manifests retain their frozen contents.

Preparation and freeze files retain creation-time paths, configuration fingerprints and not-yet-evaluated status. Current execution settings and completion status belong to the versioned evaluation reports, rather than rewriting those historical records.
