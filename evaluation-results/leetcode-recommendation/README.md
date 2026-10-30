# LeetCode recommendation results

- [Latest title-first report](v2/experiments/title-selection-full-source-fixed/source_fix.md): 40-question collective results, with 38 saved records and two source-restriction reruns; execution provenance is retained.
- [v1/](v1/): preserved GPT-5.1 baseline on the original development topics; imported historical inference.
- [v2/](v2/): preserved initial retrieval evaluation on the fresh-topic benchmark, with its original configuration.
- [v2/experiments/shortlist-30/](v2/experiments/shortlist-30/): previous pattern-based workflow with shortlist 30.
- [v2/experiments/operation-queries/](v2/experiments/operation-queries/): reverted operation-query experiment at shortlist 30, retained as history; [comparison](v2/experiments/operation-queries/comparison.md).
- [Initial title-first run](v2/experiments/title-selection-full/summary.md) and [six-question recovery](v2/experiments/title-selection-full-recovered/recovery.md): preserved earlier results and failure diagnostics.

Each run writes only its configured version directory. Historical v1 report bytes and settings are retained. Dataset versions differ, so their results are descriptive comparisons rather than a controlled model or algorithm ablation.

The latest title-first results combine saved evaluations with targeted reruns, rather than a fresh homogeneous run of the latest code. Historical retrieval results remain available. The batched full-PDF workflow has not had a full benchmark run.
