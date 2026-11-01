"""Generate document-QA answers through the production RAG, then judge those answers."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from evaluate_qa_answers import ROOT, atomic_json, main as judge_answers

CONFIG_PATH = ROOT / "config.yml"


def load_dataset(path):
    records = []
    seen_ids = set()

    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid dataset JSON on line {line_number}: {error}") from error

            question_id = record.get("id")
            if not isinstance(question_id, str) or not question_id:
                raise ValueError(f"Dataset line {line_number} has no valid ID.")
            if question_id in seen_ids:
                raise ValueError(f"Duplicate dataset ID: {question_id}")

            seen_ids.add(question_id)
            records.append(record)

    return records


def record_is_quarantined(record):
    statuses = [
        record.get("evaluation_eligibility", ""),
        record.get("review_status", ""),
        record.get("review", {}).get("status", ""),
    ]
    return any("quarantin" in str(status).lower() for status in statuses)


def record_is_eligible(record):
    review_status = record.get("review_status") or record.get("review", {}).get("status")
    review_method = (
        record.get("review_method")
        or record.get("review", {}).get("review_method")
        or record.get("review", {}).get("method")
    )
    eligibility = record.get("evaluation_eligibility", "eligible")

    return (
        review_status == "reviewed_and_verified"
        and review_method == "codex_source_audit"
        and eligibility == "eligible"
        and not record_is_quarantined(record)
    )


def collect_predictions(records, pipeline):
    results = []
    for index, record in enumerate(records, start=1):
        print(f"[{index}/{len(records)}] {record['id']}", flush=True)
        result = dict(id=record["id"], question=record["question"], reference_answer=record["reference_answer"],
            required_facts=record.get("atomic_required_facts", []), reference_evidence=record.get("evidence_records", []),
            required_evidence_groups=record.get("required_evidence_groups", []), answerability=record["answerability"],
            allowed_sources=record.get("allowed_sources", []), errors=[])
        try:
            output = pipeline.run(record["question"])
            result.update(generated_answer=output["generated_answer"], final_context=output["final_context"],
                          selected_sources=output.get("selected_sources", []))
        except Exception as error:
            result.update(generated_answer="", final_context="", selected_sources=[],
                          errors=[f"Pipeline call failed: {type(error).__name__}"])
        results.append(result)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Generate and judge only the first N eligible answers.")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be a positive integer")
    config = yaml.safe_load(CONFIG_PATH.read_text())
    path = ROOT / config["qa_answer_evaluation"]["input_path"]
    if path.resolve() == (ROOT / config["document_qa_evaluation"]["results_dir"] / "details.json").resolve():
        raise ValueError("Saved predictions must use a separate input file so reports cannot overwrite them.")
    records = load_dataset(ROOT / config["document_qa_evaluation"]["dataset_path"])
    eligible = [r for r in records if record_is_eligible(r)]
    selected = eligible[:args.limit] if args.limit else eligible
    if not selected:
        raise ValueError("No eligible evaluation examples were selected.")
    if config["indexing"]["mode"] == "build":
        # A build always indexes the complete corpus so the persisted data can be
        # reused by later queries and evaluation subsets.
        pdf_paths = sorted(ROOT.glob(config["documents"]["pdf_glob"]))
        if not pdf_paths:
            raise FileNotFoundError("No PDF files were found.")
    else:
        pdf_paths = []
    from main import RAGPipeline
    pipeline = RAGPipeline(config, pdf_paths)
    predictions = collect_predictions(selected, pipeline)
    run = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), full_dataset=args.limit is None,
        requested_limit=args.limit, evaluated_questions=len(selected), model_id=config["llm"]["model_id"],
        llm_provider=config["llm"].get("provider", "local"),
        azure_settings={k:config["llm"]["azure"][k] for k in ("base_url", "reasoning_effort", "timeout_seconds", "max_retries")}
                       if config["llm"].get("provider")=="azure_openai" else None,
        dataset_path=config["document_qa_evaluation"]["dataset_path"], config_path="config.yml",
        indexing_mode=config["indexing"]["mode"], persist_directory=config["indexing"]["persist_directory"],
        ablation=dict(config["ablation"]), embedding_model=config["embedding"]["model_name"],
        reranker_model=config["reranking"]["model_name"], reranker_include_source_name=config["reranking"]["include_source_name"],
        text_normalization=pipeline.persisted_index_settings()["text_normalization"],
        query_expansion_settings=dict(config["query_expansion"]), chunk_size=config["chunking"]["chunk_size"],
        chunk_overlap=config["chunking"]["chunk_overlap"], dense_index_type=config["retrieval"]["dense_index_type"],
        dense_top_k=config["retrieval"]["dense_top_k"], bm25_top_k=config["retrieval"]["bm25_top_k"],
        final_top_k=config["reranking"]["final_top_k"], answer_max_new_tokens=config["llm"]["generation"]["max_new_tokens"])
    counts = dict(total=len(records), eligible=len(eligible), excluded=len(records)-len(eligible),
                  quarantined=sum(record_is_quarantined(r) for r in records))
    counts["unresolved"] = counts["excluded"]-counts["quarantined"]
    atomic_json(path, dict(schema_version="1.0.0", run=run, dataset_counts=counts, questions=predictions))
    print(f"Saved {len(predictions)} answers and their grounding context to {path}", flush=True)
    judge_answers(["--limit", str(args.limit)] if args.limit else [])


if __name__ == "__main__":
    main()
