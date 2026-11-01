"""Report QA judge agreement against 48 source-audited cases, evaluated twice."""
import argparse
import csv
import hashlib
import json
import logging
import os
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pypdf
import yaml

from evaluate_qa_answers import (ROOT, AnswerJudge, FACT_LABELS, CLAIM_LABELS,
                                ABSTENTION_LABELS, atomic_json, digest, normalized, judge_protocol)


def payload_for_case(case):
    # Expected labels, rationales, roles, and annotations must never reach the judge.
    payload = {key: case[key] for key in ("question", "generated_answer")}
    if case["stage"] == "coverage":
        payload.update(reference_answer=case["reference_answer"], required_facts=[
            {key: fact[key] for key in ("text", "evidence_quotes")} for fact in case["required_facts"]])
    elif case["stage"] == "grounding":
        payload["retrieved_context"] = case["retrieved_context"]
    else:
        payload.update({key:case[key] for key in ("reference_answer", "allowed_sources")})
    return payload


def assess_case(case, judgment):
    expected = case["expected_labels"]
    if judgment["status"] != "valid":
        return dict(exact_match=False, inventory_ok=None,
                    comparisons=[dict(expected=label, predicted="<unscored>") for label in expected or ["<no_claims>"]])
    value = judgment["result"]
    if case["stage"] != "grounding":
        predicted = [item["label"] for item in value["facts"]] if case["stage"] == "coverage" else [value["label"]]
        rows = [dict(expected=label, predicted=predicted[i] if i < len(predicted) else "<missing>") for i,label in enumerate(expected)]
        exact = predicted == expected
        return dict(exact_match=exact, inventory_ok=None, comparisons=rows)
    claims = case["expected_claims"]
    predicted = value["claims"]
    if not claims:
        rows = [dict(expected="<no_claims>", predicted=item["label"]) for item in predicted]
        return dict(exact_match=not predicted, inventory_ok=not predicted,
                    comparisons=rows or [dict(expected="<no_claims>", predicted="<no_claims>")])
    matched, rows, extra = set(), [], 0
    for item in predicted:
        quote = normalized(item["answer_quote"])
        # Span containment permits harmless quote boundary differences. Ambiguity is
        # counted as an inventory mismatch, never resolved using the predicted label.
        candidates = [i for i,claim in enumerate(claims)
                      if quote and (quote in normalized(claim["answer_quote"])
                                    or normalized(claim["answer_quote"]) in quote)]
        if len(candidates) != 1 or candidates[0] in matched:
            rows.append(dict(expected="<extra_claim>", predicted=item["label"]))
            extra += 1
        else:
            index = candidates[0]
            matched.add(index)
            rows.append(dict(expected=claims[index]["label"], predicted=item["label"], claim_id=claims[index]["claim_id"]))
    for i,claim in enumerate(claims):
        if i not in matched:
            rows.append(dict(expected=claim["label"], predicted="<missing_claim>", claim_id=claim["claim_id"]))
    inventory_ok = len(matched) == len(claims) and not extra
    return dict(exact_match=inventory_ok and all(row["expected"] == row["predicted"] for row in rows),
                inventory_ok=inventory_ok, comparisons=rows)


def evaluate_case(case, judge):
    judgment = judge.ask(case["stage"], payload_for_case(case))
    return dict(id=case["id"], stage=case["stage"], partition=case["partition"], expected_labels=case["expected_labels"],
                judgment=judgment, assessment=assess_case(case, judgment), llm_calls=judge.calls,
                token_usage=dict(judge.tokens), judge_models=dict(judge.models))


def summarize(results):
    def accuracy(items):
        correct = sum(item["assessment"]["exact_match"] for item in items)
        return dict(correct=correct,total=len(items),score=correct/len(items) if items else None)
    groups = {part:accuracy([r for r in results if r["partition"]==part]) for part in ("development", "reserved")}
    valid = sum(r["judgment"]["status"]=="valid" for r in results)
    stages = {}
    for stage,labels in (("coverage", FACT_LABELS[:-1]), ("grounding", CLAIM_LABELS[:-1]), ("abstention", ABSTENTION_LABELS[:-1])):
        records = [r for r in results if r["stage"]==stage]
        matrix = Counter((row["expected"],row["predicted"]) for r in records for row in r["assessment"]["comparisons"])
        per_label = {}
        for label in labels:
            tp = matrix[label,label]
            expected = sum(count for (gold,pred),count in matrix.items() if gold==label)
            predicted = sum(count for (gold,pred),count in matrix.items() if pred==label)
            per_label[label] = dict(support=expected,predicted=predicted,true_positive=tp,
                precision=tp/predicted if predicted else 0,recall=tp/expected if expected else 0,
                f1=2*tp/(expected+predicted) if expected+predicted else 0)
        f1s = [m["f1"] for m in per_label.values() if m["support"] or m["predicted"]]
        stages[stage] = dict(exact_case_accuracy=accuracy(records),per_label=per_label,
                            macro_f1=sum(f1s)/len(f1s) if f1s else None,
                            confusion=[dict(expected=gold,predicted=pred,count=count) for (gold,pred),count in sorted(matrix.items())])
    rate = valid/len(results) if results else None
    return dict(exact_case_accuracy=accuracy(results),partitions=groups,stages=stages,
                usable_judgments=valid,unscored_judgments=len(results)-valid,usable_judgment_rate=rate)


def trial_summaries(results, case_count):
    trials = sorted({r["trial"] for r in results})
    values = {str(trial):summarize([r for r in results if r["trial"]==trial]) for trial in trials}
    indexed = {(r["id"],r["trial"]):r for r in results}
    comparable, consistent, pairs = 0, 0, 0
    def signature(result):
        rows=result["assessment"]["comparisons"]
        if result["stage"]=="grounding":
            return sorted((row.get("claim_id",""),row["expected"],row["predicted"]) for row in rows)
        return [(row["expected"],row["predicted"]) for row in rows]
    for trial in trials[1:]:
        for identifier in {r["id"] for r in results}:
            a,b=indexed.get((identifier,trials[0])),indexed.get((identifier,trial))
            if a is None or b is None:
                continue
            pairs+=1
            if a["judgment"]["status"]==b["judgment"]["status"]=="valid":
                comparable+=1
                consistent+=signature(a)==signature(b)
    return {"trials":values, "combined":summarize(results), "case_count":case_count,
            "repeatability":dict(paired_cases=pairs,both_usable=comparable,consistent=consistent,
                                 conditional_agreement=consistent/comparable if comparable else None,
                                 usable_and_consistent_rate=consistent/pairs if pairs else None)}


def verify_inputs(cases, manifest, dataset_path):
    if digest(dataset_path) != manifest["dataset_sha256"]:
        raise ValueError("Dataset bytes differ from the frozen manifest.")
    if len(cases)!=manifest["case_count"] or len({c["id"] for c in cases})!=len(cases):
        raise ValueError("Invalid case count or duplicate case IDs.")
    corpus_path = ROOT / manifest["corpus_manifest_path"]
    if digest(corpus_path) != manifest["corpus_manifest_sha256"]:
        raise ValueError("Corpus manifest differs from the frozen version.")
    corpus=json.loads(corpus_path.read_text())
    documents={d["source"]:d for d in corpus["documents"]}
    for doc in documents.values():
        with (ROOT/doc["relative_path"]).open("rb") as file:
            if hashlib.file_digest(file,"sha256").hexdigest()!=doc["sha256"]:
                raise ValueError(f"PDF hash mismatch: {doc['source']}")
    readers,pages={},{}
    for anchor in manifest["source_anchors"].values():
        source,page=anchor["source"],anchor["pdf_page"]
        if source not in documents or anchor["source_sha256"]!=documents[source]["sha256"]:
            raise ValueError("Unknown source or incorrect anchor source hash.")
        if source not in readers:
            readers[source]=pypdf.PdfReader(ROOT/documents[source]["relative_path"])
        if not 1<=page<=len(readers[source].pages):
            raise ValueError("Invalid physical PDF page.")
        if (source,page) not in pages:
            pages[source,page]=readers[source].pages[page-1].extract_text() or ""
        if pages[source,page][anchor["start"]:anchor["end_exclusive"]]!=anchor["exact_quote"]:
            raise ValueError("Reference quote/offsets do not match the cited original PDF page.")
    for case in cases:
        labels={"coverage":FACT_LABELS,"grounding":CLAIM_LABELS,"abstention":ABSTENTION_LABELS}[case["stage"]]
        if any(label not in labels for label in case["expected_labels"]) or case["partition"] not in ("development","reserved"):
            raise ValueError("Unknown expected label or case partition.")
        if any(identifier not in manifest["source_anchors"] for identifier in case["source_anchor_ids"]):
            raise ValueError("Unknown source anchor.")
        if case["stage"]=="coverage" and len(case["required_facts"])!=len(case["expected_labels"]):
            raise ValueError("Required fact and expected label counts differ.")
        if case["stage"]=="abstention" and len(case["expected_labels"])!=1:
            raise ValueError("Abstention requires one expected label.")
        if case["stage"]=="grounding":
            claims=case["expected_claims"]
            if [c["label"] for c in claims]!=case["expected_labels"]:
                raise ValueError("Expected claim labels differ.")
            for claim in claims:
                if case["generated_answer"][claim["answer_start"]:claim["answer_end_exclusive"]]!=claim["answer_quote"]:
                    raise ValueError("Expected answer claim is not at its declared character offsets.")
    return dict(source_anchors_verified=len(manifest["source_anchors"]),pdf_pages_read=len(pages),pdf_hashes_verified=len(documents))


def write_reports(directory, run, cases, results, manifest):
    metrics = trial_summaries(results, manifest["case_count"])
    fmt = lambda x: f"{x:.1%}" if x is not None else "N/A"
    count = lambda m: f"{m['correct']}/{m['total']} ({fmt(m['score'])})"
    lines = ["# QA judge performance", "",
        f"The latest Azure OpenAI `{run['judge_settings']['model_id']}` judge was evaluated on {len({r['id'] for r in results})} distinct cases in {run['repetitions']} runs. "
        "Exact agreement requires all expected labels and the claim inventory to match. Unscored judgments remain in the denominator.", "",
        "| Run | Exact case agreement | Valid judgments | Unscored |", "|---|---:|---:|---:|"]
    for trial, values in metrics["trials"].items():
        total = values["exact_case_accuracy"]["total"]
        lines.append(f"| {trial} | {count(values['exact_case_accuracy'])} | {values['usable_judgments']}/{total} | {values['unscored_judgments']} |")
    combined = metrics["combined"]
    lines += ["", f"**Combined agreement: {count(combined['exact_case_accuracy'])}.** "
              "Repeated judgments are not additional distinct cases.", "",
              "## Case composition", "",
              "The benchmark includes 30 development cases that informed judge improvements and 18 reserved cases not used to refine this judge. "
              "The combined score mixes these groups and does not establish independent test accuracy. "
              "Expected labels are automatically source-audited, not human-approved. There is no pass/fail qualification threshold.", "",
              "| Group | " + " | ".join(f"Run {t}" for t in metrics["trials"]) + " |",
              "|---|" + "---:|"*len(metrics["trials"])]
    for part in ("development", "reserved"):
        lines.append(f"| {part.capitalize()} | " + " | ".join(count(m["partitions"][part]) for m in metrics["trials"].values()) + " |")
    lines += ["", "## Tasks", "", "| Task | " + " | ".join(f"Run {t}" for t in metrics["trials"]) + " |",
              "|---|" + "---:|"*len(metrics["trials"])]
    for stage in ("coverage", "grounding", "abstention"):
        lines.append(f"| {stage.capitalize()} | " + " | ".join(count(m["stages"][stage]["exact_case_accuracy"]) for m in metrics["trials"].values()) + " |")
    repeat = metrics["repeatability"]
    lines += ["", "## Consistency", "",
        f"Usable and identical label/inventory decisions on {repeat['consistent']}/{repeat['paired_cases']} repeated pairs ({fmt(repeat['usable_and_consistent_rate'])}). "
        f"Among pairs with two valid judgments, agreement was {repeat['consistent']}/{repeat['both_usable']} ({fmt(repeat['conditional_agreement'])}). "
        "Consistency alone does not establish correctness.", "",
        "## Errors and unscored judgments", "", "| Case | Run | Expected labels | Observed labels | Status |", "|---|---:|---|---|---|"]
    failures = [r for r in results if not r["assessment"]["exact_match"]]
    for r in failures:
        observed = ", ".join(c["predicted"] for c in r["assessment"]["comparisons"])
        lines.append(f"| {r['id']} | {r['trial']} | `{', '.join(r['expected_labels']) or 'no claims'}` | `{observed}` | `{r['judgment']['status']}` |")
    if not failures:
        lines.append("| None | | | | |")
    lines += ["", "All judgments, reasons, source/context quotes, exclusions, confusion counts, and per-label precision/recall/F1 are in [details.json](details.json). "
              "[per_case.csv](per_case.csv) contains one row per case/run. "
              "[Dataset and evidence](../../../evaluation-data/qa-judge-validation/README.md).", "",
              "## Provenance", "",
              f"- Reporting mode: `{run.get('origin', 'live_judging')}`. Saved judgments were not relabeled during consolidation.",
              f"- Returned model IDs: `{run['returned_models']}`.",
              f"- Dataset SHA-256: `{run['dataset_sha256']}`.",
              f"- Judge protocol SHA-256: `{run['judge_protocol_sha256']}`.",
              f"- Source verification: `{run['source_verification']}`."]
    tokens = Counter()
    for r in results:
        tokens.update(r["token_usage"])
    lines += [f"- Recorded calls for these judgments: {sum(r['llm_calls'] for r in results)}. Recorded tokens: `{dict(tokens)}`. "
              "SDK retries may add requests. Usage is not a bill.", "",
              "These are judge-validation results, not RAG answer-quality or retrieval scores. Literal quote checks establish provenance, not semantic entailment. "
              "Unmatched or ambiguous claim mappings count as inventory errors. No-claim controls affect case agreement but are not a semantic class in macro F1.", ""]
    directory.mkdir(parents=True, exist_ok=True)
    details = dict(schema_version="1.1.0", run=run, metric_summaries=metrics, questions=results)
    with tempfile.TemporaryDirectory(dir=directory.parent, prefix=".judge-report-") as temporary:
        stage = Path(temporary)
        atomic_json(stage/"details.json", details)
        (stage/"summary.md").write_text("\n".join(lines))
        by_id = {c["id"]:c for c in cases}
        with (stage/"per_case.csv").open("w", newline="") as file:
            fields = ["case_id", "trial", "stage", "partition", "question", "generated_answer", "expected_labels", "predicted_labels", "exact_match", "judge_status", "inventory_ok"]
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for r in results:
                writer.writerow(dict(case_id=r["id"], trial=r["trial"], stage=r["stage"], partition=r["partition"],
                    question=by_id[r["id"]]["question"], generated_answer=by_id[r["id"]]["generated_answer"],
                    expected_labels=json.dumps(r["expected_labels"]),
                    predicted_labels=json.dumps([row["predicted"] for row in r["assessment"]["comparisons"]]),
                    exact_match=r["assessment"]["exact_match"], judge_status=r["judgment"]["status"], inventory_ok=r["assessment"]["inventory_ok"]))
        for name in ("summary.md", "details.json", "per_case.csv"):
            os.replace(stage/name, directory/name)
    return metrics


def run_identity(config, dataset_path, manifest_path, limit):
    return dict(dataset_sha256=digest(dataset_path), manifest_sha256=digest(manifest_path),
                judge_protocol_sha256=judge_protocol(config), reporting_code_sha256=digest(__file__),
                repetitions=config["qa_judge_validation"]["repetitions"], limit=limit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args()
    if (args.limit is not None and args.limit<1) or (args.resume and args.restart):
        parser.error("Use a positive limit, and choose --resume or --restart.")
    config = yaml.safe_load((ROOT/"config.yml").read_text())
    settings = config["qa_judge_validation"]
    dataset_path, manifest_path = ROOT/settings["dataset_path"], ROOT/settings["manifest_path"]
    cases = [json.loads(line) for line in dataset_path.read_text().splitlines() if line.strip()]
    manifest = json.loads(manifest_path.read_text())
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    source_verification = verify_inputs(cases, manifest, dataset_path)
    print(f"Verified {len(cases)} cases: {source_verification}", flush=True)
    if args.verify_only:
        return
    for key in ("max_workers", "repetitions"):
        if type(settings[key]) is not int or settings[key]<1:
            raise ValueError(f"{key} must be a positive integer.")
    selected = cases[:args.limit] if args.limit else cases
    identity = run_identity(config, dataset_path, manifest_path, args.limit)
    directory = ROOT/settings["results_dir"]
    checkpoint_path = directory/".checkpoint"/"validation.json"
    checkpoint = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() and not args.restart else None
    if checkpoint and not args.resume and not checkpoint.get("complete"):
        raise ValueError("Unfinished evaluation exists. Use --resume or --restart.")
    if args.resume and checkpoint and checkpoint["identity"]!=identity:
        raise ValueError("Judge inputs, protocol, or reporting code changed. Cannot resume.")
    if not args.resume or not checkpoint:
        checkpoint = dict(identity=identity, complete=False, results={}, provenance=dict(origin="live_judging",
            inference_code_sha256=digest(ROOT/"evaluate_qa_answers.py"), started_utc=datetime.now(timezone.utc).isoformat()))
    tasks = [(case, trial) for trial in range(1, settings["repetitions"]+1) for case in selected]
    pending = [(c,t) for c,t in tasks if f"{c['id']}::{t}" not in checkpoint["results"]]
    atomic_json(checkpoint_path, checkpoint)
    def work(case, trial):
        print(f"Starting {case['id']} run {trial} ({case['stage']})", flush=True)
        return {**evaluate_case(case, AnswerJudge(config)), "trial":trial}
    with ThreadPoolExecutor(max_workers=settings["max_workers"]) as pool:
        futures = {pool.submit(work,c,t):f"{c['id']}::{t}" for c,t in pending}
        for future in as_completed(futures):
            result = future.result()
            checkpoint["results"][futures[future]] = result
            atomic_json(checkpoint_path, checkpoint)
            print(f"Finished {result['id']} run {result['trial']}: {len(checkpoint['results'])}/{len(tasks)}, exact={result['assessment']['exact_match']}", flush=True)
    results = [checkpoint["results"][f"{c['id']}::{t}"] for c,t in tasks]
    run = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), **checkpoint["provenance"], **identity,
        judge_settings={k:v for k,v in config["qa_answer_evaluation"].items() if k not in ("input_path", "results_dir", "max_workers")},
        azure_settings={k:config["llm"]["azure"][k] for k in ("base_url", "api_key_env", "reasoning_effort", "max_retries")},
        dataset_path=settings["dataset_path"], returned_models=sorted({m for r in results for m in r["judge_models"]}),
        source_verification=source_verification, requested_workers=settings["max_workers"],
        resumed=args.resume, reused_judgments=len(tasks)-len(pending))
    metrics = write_reports(directory, run, cases, results, manifest)
    checkpoint["complete"] = True
    atomic_json(checkpoint_path, checkpoint)
    print(json.dumps({"runs":{t:v["exact_case_accuracy"] for t,v in metrics["trials"].items()},
                      "combined":metrics["combined"]["exact_case_accuracy"]}, indent=2), flush=True)
    print(f"Saved {directory/'summary.md'}", flush=True)


if __name__=="__main__":
    main()
