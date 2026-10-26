# Evaluation data

- [document-qa/](document-qa/): 50 document-QA questions with atomic answers and annotated passages, evaluated by `evaluate_document_qa.py`.
- [leetcode-recommendation/](leetcode-recommendation/): 40 related-problem requests with source-grounded relevance labels, evaluated by `evaluate_leetcode_recommendation.py`.

Both are fixed comparison benchmarks, not held-out datasets. Original PDFs belong in the ignored `documents/` directory. Each benchmark pins the corpus and uses one-based physical PDF pages, not printed book labels.
