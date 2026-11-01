"""Judge saved QA answers without running retrieval, reranking, or answer generation."""
import argparse
import csv
import hashlib
import json
import os
import re
import statistics
import tempfile
import time
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
FACT_LABELS = ("covered", "missing_or_incomplete", "contradicted", "uncertain")
CLAIM_LABELS = ("supported", "unsupported", "contradicted", "uncertain")
ABSTENTION_LABELS = ("appropriate_abstention", "unsupported_answer", "mixed", "uncertain")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".writing-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def normalized(text):
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"(?<=\w)[-\u00ad\u2010\u2011][\t ]*\r?\n[\t ]*(?=\w)", "", text)
    return " ".join(text.split())


def grounding_text(answer):
    # Remove only whole citation rows. Keep prose, inline citations, and all
    # substantive claims. Original answers and original character offsets survive.
    citation = re.compile(r"\s*(?:[-*]\s*)?SOURCE:\s*[^\n]+?\.pdf,\s*PAGES?:\s*\d+(?:\s*[-–,]\s*\d+)*\s*", re.I)
    kept, removed, offset = [], [], 0
    for line in answer.splitlines(keepends=True):
        if citation.fullmatch(line.rstrip("\r\n")):
            removed.append(dict(start=offset, end_exclusive=offset+len(line), text=line))
            # Keep a separator so neighboring prose is never joined into a claim.
            kept.append("\n")
        else:
            kept.append(line)
        offset += len(line)
    return "".join(kept), removed


def object_schema(properties):
    return dict(type="object", properties=properties, required=list(properties), additionalProperties=False)


def response_schema(stage):
    string = {"type": "string"}
    if stage == "claim_extraction":
        statement = object_schema(dict(kind={"type":"string", "enum":["substantive", "abstention", "context_insufficiency"]},
                                       answer_quote=string, reason=string))
        return object_schema(dict(statements={"type":"array", "items":statement}))
    labels = FACT_LABELS if stage == "coverage" else CLAIM_LABELS if stage == "grounding" else ABSTENTION_LABELS
    item = object_schema(dict(label={"type": "string", "enum": list(labels)}, answer_quote=string, reason=string))
    if stage == "grounding":
        item["properties"]["context_quotes"] = {"type": "array", "items": string}
        item["required"].append("context_quotes")
        return object_schema(dict(claims={"type": "array", "items": item}, no_claims_reason=string))
    if stage == "coverage":
        return object_schema(dict(facts={"type": "array", "items": item}))
    item["properties"].update(acknowledges_insufficiency={"type": "boolean"}, provides_substantive_answer={"type": "boolean"})
    item["required"] += ["acknowledges_insufficiency", "provides_substantive_answer"]
    return item


def validate_judgment(stage, value, payload):
    if not isinstance(value, dict):
        raise ValueError("Return a JSON object.")
    if stage == "claim_extraction":
        statements=value.get("statements")
        if not isinstance(statements,list):
            raise ValueError("Return a statements list with explicit substantive/abstention/context_insufficiency kinds.")
        seen=set()
        for entry in statements:
            quote=entry.get("answer_quote") if isinstance(entry,dict) else None
            if (not isinstance(quote,str) or not normalized(quote) or normalized(quote) in seen
                    or normalized(quote) not in normalized(payload["generated_answer"])
                    or entry.get("kind") not in ("substantive","abstention","context_insufficiency")
                    or not isinstance(entry.get("reason"),str) or not entry["reason"].strip()):
                raise ValueError("Each extracted statement needs a unique literal answer quote, valid kind, and reason.")
            seen.add(normalized(quote))
        return value
    items = value.get("facts") if stage == "coverage" else value.get("claims") if stage == "grounding" else [value]
    labels = FACT_LABELS if stage == "coverage" else CLAIM_LABELS if stage == "grounding" else ABSTENTION_LABELS
    if not isinstance(items, list) or (stage == "coverage" and len(items) != len(payload["required_facts"])):
        raise ValueError("Return one fact entry per input fact, or a claims list for grounding.")
    if stage == "grounding":
        reason = value.get("no_claims_reason")
        if not isinstance(reason, str) or (not items and not reason.strip()) or (items and reason.strip()):
            raise ValueError("Explain an empty claims list using no_claims_reason; otherwise set it to an empty string.")
        excluded = value.get("excluded_statements", [])
        if not isinstance(excluded, list):
            raise ValueError("Return an excluded_statements list for abstention/context-insufficiency text.")
        for entry in excluded:
            if (not isinstance(entry, dict) or entry.get("kind") not in ("abstention", "context_insufficiency")
                    or not isinstance(entry.get("reason"), str) or not entry["reason"].strip()
                    or not isinstance(entry.get("answer_quote"), str) or not normalized(entry["answer_quote"])
                    or normalized(entry["answer_quote"]) not in normalized(payload["generated_answer"])):
                raise ValueError("Every excluded statement needs a literal answer quote, exclusion kind, and reason.")
        if {normalized(e["answer_quote"]) for e in excluded} & {normalized(e.get("answer_quote", "")) for e in items}:
            raise ValueError("A statement cannot be both excluded and counted as a factual claim.")
    if stage == "abstention":
        flags = [value.get(key) for key in ("acknowledges_insufficiency", "provides_substantive_answer")]
        if any(type(flag) is not bool for flag in flags):
            raise ValueError("State both abstention behavior flags as booleans.")
        expected = "mixed" if all(flags) else "appropriate_abstention" if flags[0] else "unsupported_answer" if flags[1] else "uncertain"
        if value.get("label") not in (expected, "uncertain"):
            raise ValueError(f"Behavior flags require label {expected}: an insufficiency acknowledgment plus a guess is mixed.")
    seen = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict) or item.get("label") not in labels:
            raise ValueError(f"Item {index + 1} has an invalid label.")
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            raise ValueError(f"Item {index + 1} needs a short reason.")
        quote = item.get("answer_quote")
        required = stage != "coverage" or item["label"] in ("covered", "contradicted")
        if not isinstance(quote, str) or (required and not normalized(quote)):
            raise ValueError(f"Item {index + 1} needs an answer_quote.")
        if quote and normalized(quote) not in normalized(payload["generated_answer"]):
            raise ValueError(f"Item {index + 1} answer_quote is not a consecutive excerpt of the answer.")
        if stage == "grounding":
            if normalized(quote) in seen:
                raise ValueError(f"Item {index + 1} duplicates a claim quote.")
            seen.add(normalized(quote))
            context_quotes = item.get("context_quotes")
            if not isinstance(context_quotes, list) or (item["label"] in ("supported", "contradicted") and not context_quotes):
                raise ValueError(f"Item {index + 1} needs supporting or contradicting context_quotes.")
            for context_quote in context_quotes:
                if (not isinstance(context_quote, str) or not normalized(context_quote)
                        or normalized(context_quote) not in normalized(payload["retrieved_context"])):
                    raise ValueError(f"Item {index + 1} context_quote is not a consecutive excerpt of the supplied context.")
    return value


class AnswerJudge:
    def __init__(self, config, client=None):
        self.settings = config["qa_answer_evaluation"]
        self.azure = config["llm"]["azure"]
        self.calls, self.tokens, self.models = 0, Counter(), Counter()
        if client is None:
            from dotenv import load_dotenv
            from openai import OpenAI
            load_dotenv(ROOT / ".env")
            key = os.environ.get(self.azure["api_key_env"], "").strip()
            if not key:
                raise ValueError(f"Set {self.azure['api_key_env']} in the local environment or .env.")
            client = OpenAI(base_url=self.azure["base_url"].rstrip("/") + "/", api_key=key,
                            timeout=self.settings["timeout_seconds"], max_retries=self.azure["max_retries"])
        self.client = client

    def ask(self, stage, payload):
        original_payload = payload
        preprocessing = None
        if stage == "grounding":
            text, removed = grounding_text(payload["generated_answer"])
            payload = {**payload, "generated_answer": text}
            preprocessing = dict(removed_citation_rows=removed)
            if not text.strip():
                return dict(status="valid", result=dict(claims=[], excluded_statements=[],
                    no_claims_reason="Only citation metadata remains after deterministic preprocessing."),
                    errors=[], reason=None, preprocessing=preprocessing)
            extraction=self.ask("claim_extraction",{key:payload[key] for key in ("question","generated_answer")})
            preprocessing["claim_extraction"]=extraction
            if extraction["status"]!="valid":
                return dict(status="unscored",result=None,errors=extraction["errors"],
                            reason="Claim extraction failed.",preprocessing=preprocessing)
            statements=extraction["result"]["statements"]
            factual=[s["answer_quote"] for s in statements if s["kind"]=="substantive"]
            excluded=[s for s in statements if s["kind"]!="substantive"]
            if not factual:
                return dict(status="valid",result=dict(claims=[],excluded_statements=excluded,
                            no_claims_reason="Extraction found only abstention/context-insufficiency or formatting."),
                            errors=[],reason=None,preprocessing=preprocessing)
            # The grounding judge never sees excluded statements. Python retains
            # them separately and requires one judgment for every extracted claim.
            payload={**payload,"generated_answer":"\n\n".join(factual),"claims_to_judge":factual}
        errors, feedback = [], ""
        for _ in range(self.settings["validation_retries"] + 1):
            self.calls += 1
            try:
                response = self.client.chat.completions.create(
                    model=self.settings["model_id"], reasoning_effort=self.azure["reasoning_effort"],
                    max_completion_tokens=self.settings["max_new_tokens"], store=False,
                    response_format={"type": "json_schema", "json_schema": {
                        "name": "qa_" + stage, "strict": True, "schema": response_schema(stage)}},
                    messages=[{"role": "system", "content": self.settings["system_prompt"]},
                              {"role": "user", "content": self.settings[stage + "_prompt"] + feedback
                               + "\n\nINPUT DATA:\n" + json.dumps(payload, ensure_ascii=False)}])
                if response.usage:
                    self.tokens.update({key: getattr(response.usage, key) for key in
                                        ("prompt_tokens", "completion_tokens", "total_tokens")})
                self.models.update([response.model])
                choice = response.choices[0]
                if choice.finish_reason != "stop" or not choice.message.content:
                    raise ValueError("Judge response was incomplete or refused.")
                result = validate_judgment(stage, json.loads(choice.message.content), payload)
                if stage=="claim_extraction":
                    return dict(status="valid",result=result,errors=errors,reason=None)
                if stage=="grounding":
                    if Counter(normalized(c["answer_quote"]) for c in result["claims"])!=Counter(map(normalized,factual)):
                        raise ValueError("Judge each claims_to_judge quote exactly once. Copy its entire answer_quote without splitting or omitting it.")
                    result["excluded_statements"]=excluded
                # Removing a citation row must not create a quote absent from the original.
                validate_judgment(stage, result, original_payload)
                uncertain = any(item["label"] == "uncertain" for item in (
                    result["facts"] if stage == "coverage" else result["claims"] if stage == "grounding" else [result]))
                return dict(status="unscored" if uncertain else "valid", result=result,
                            errors=errors, reason="Judge expressed uncertainty." if uncertain else None,
                            **({"preprocessing": preprocessing} if preprocessing is not None else {}))
            except (ValueError, KeyError, TypeError) as error:
                errors.append(str(error))
                feedback = "\nCORRECTION: " + str(error) + " Return complete JSON with literal quotes from INPUT DATA."
            except Exception as error:
                # Do not serialize SDK exceptions: their messages may contain request details.
                return dict(status="unscored", result=None, errors=errors + [type(error).__name__],
                            reason="API request failed.",
                            **({"preprocessing": preprocessing} if preprocessing is not None else {}))
        return dict(status="unscored", result=None, errors=errors, reason="Validation failed after one corrective retry.",
                    **({"preprocessing": preprocessing} if preprocessing is not None else {}))


def evaluate_saved_answer(question, judge):
    started = time.monotonic()
    result = dict(id=question["id"], question=question["question"], generated_answer=question["generated_answer"],
                  reference_answer=question["reference_answer"])
    result.update({key:question[key] for key in ("required_facts", "reference_evidence", "answerability",
                   "allowed_sources", "final_context", "errors") if key in question})
    if question.get("errors") or not question.get("generated_answer", "").strip():
        result["judgments"] = {stage: dict(status="unscored", result=None, reason="Saved pipeline execution failed or answer is empty.")
                               for stage in ("coverage", "grounding", "abstention")}
    else:
        base = dict(question=question["question"], generated_answer=question["generated_answer"])
        unanswerable = question["answerability"]["label"] == "unanswerable_within_allowed_sources"
        judgments = {}
        if unanswerable:
            judgments["coverage"] = dict(status="not_applicable", result=None)
            judgments["abstention"] = judge.ask("abstention", {**base, "reference_answer": question["reference_answer"],
                                                            "allowed_sources": question["allowed_sources"]})
        else:
            payload = {**base, "reference_answer": question["reference_answer"],
                       "required_facts": [{"text": fact["text"], "evidence_quotes": [e["exact_quote"]
                            for e in question["reference_evidence"] if e["evidence_id"] in fact["evidence_ids"]]}
                            for fact in question["required_facts"]]}
            judgments["coverage"] = judge.ask("coverage", payload)
            if judgments["coverage"]["result"]:
                for fact, label in zip(question["required_facts"], judgments["coverage"]["result"]["facts"]):
                    label["fact_id"] = fact["fact_id"]
                    label["required_fact"] = fact["text"]
            judgments["abstention"] = dict(status="not_applicable", result=None)
        print(f"  {question['id']}: grounding judge", flush=True)
        judgments["grounding"] = judge.ask("grounding", {**base, "retrieved_context": question["final_context"]})
        if judgments["grounding"]["result"]:
            for index, claim in enumerate(judgments["grounding"]["result"]["claims"], start=1):
                claim["claim_id"] = f"{question['id']}-c{index}"
        result["judgments"] = judgments
    result.update(seconds=time.monotonic() - started, llm_calls=judge.calls, token_usage=dict(judge.tokens),
                  judge_models=dict(judge.models))
    return result


def question_scores(question):
    judgments = question["judgments"]
    result = {}
    for stage, names, positive in (("coverage", ("fact_coverage", "reference_contradiction_rate"), "covered"),
                                   ("grounding", ("grounding_rate", "context_contradiction_rate"), "supported")):
        judgment = judgments[stage]
        items = judgment["result"]["facts" if stage == "coverage" else "claims"] if judgment.get("result") else []
        counts = Counter(item["label"] for item in items)
        status = "scored" if judgment["status"] == "valid" and items else "not_applicable" if judgment["status"] in ("valid", "not_applicable") else "unscored"
        for name, label in zip(names, (positive, "contradicted")):
            result[name] = dict(status=status, score=counts[label] / len(items) if status == "scored" else None,
                                matched=counts[label] if items else None, total=len(items) if items else None)
    abstention = judgments["abstention"]
    status = "scored" if abstention["status"] == "valid" else abstention["status"]
    result["abstention_accuracy"] = dict(status=status,
        score=int(abstention["result"]["label"] == "appropriate_abstention") if status == "scored" else None)
    return result


def summarize(questions):
    scores = [question_scores(question) for question in questions]
    return {name: dict(average=statistics.mean(s[name]["score"] for s in scores if s[name]["status"] == "scored")
                       if any(s[name]["status"] == "scored" for s in scores) else None,
                       **{status: sum(s[name]["status"] == status for s in scores)
                          for status in ("scored", "not_applicable", "unscored")})
            for name in ("fact_coverage", "reference_contradiction_rate", "grounding_rate",
                         "context_contradiction_rate", "abstention_accuracy")}


def calibration_cases(judge):
    cases = []
    coverage = dict(question="Describe the cache policy.", reference_answer="Items expire after ten seconds, capacity is 20, and items are encrypted.",
        generated_answer="Items expire after 10 seconds. The cache holds 50 items.",
        required_facts=[{"text": text, "evidence_quotes": [text]} for text in
                        ("Items expire after ten seconds.", "The capacity is 20 items.", "Items are encrypted.")])
    tests = [("fact_labels", "coverage", coverage, ["covered", "contradicted", "missing_or_incomplete"]),
             ("claim_labels", "grounding", dict(question="Describe the cache policy.",
              generated_answer="Items expire after ten seconds. Items are encrypted. Items expire immediately.",
              retrieved_context="Items expire after ten seconds. They do not expire immediately."),
              ["supported", "unsupported", "contradicted"])]
    for label, answer in [("appropriate_abstention", "The supplied context does not provide the requested policy."),
                          ("unsupported_answer", "The cache capacity is 20 items."),
                          ("mixed", "The context does not provide the capacity, but my guess is 20 items.")]:
        tests.append((label, "abstention", dict(question="What is the cache capacity?", generated_answer=answer,
                      reference_answer="The allowed source does not specify the capacity.", allowed_sources=["synthetic calibration"]), [label]))
    for name, stage, payload, expected in tests:
        judgment = judge.ask(stage, payload)
        value = judgment.get("result")
        actual = [item["label"] for item in (value["facts"] if stage == "coverage" else value["claims"] if stage == "grounding" else [value])] if value else []
        passed = judgment["status"] == "valid" and (actual == expected if stage != "grounding" else Counter(actual) == Counter(expected))
        cases.append(dict(name=name, expected=expected, actual=actual, passed=passed, judgment=judgment))
        print(f"Calibration {name}: {'PASS' if passed else 'FAIL'}", flush=True)
    return dict(cases=cases, passed=all(case["passed"] for case in cases), llm_calls=judge.calls, token_usage=dict(judge.tokens))


def judge_protocol(config):
    # Fingerprint inference separately from report paths and presentation changes.
    inference_code = Path(__file__).read_text().split("\ndef evaluate_saved_answer(", 1)[0]
    settings = {k:v for k,v in config["qa_answer_evaluation"].items() if k not in ("input_path", "results_dir", "max_workers")}
    azure = {k:config["llm"]["azure"][k] for k in ("base_url", "api_key_env", "reasoning_effort", "max_retries")}
    value = dict(inference_code=inference_code, judge_settings=settings, azure_settings=azure)
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def validation_status(config):
    # Attach measured agreement without imposing a pass/fail qualification gate.
    settings = config["qa_judge_validation"]
    path = ROOT/settings["results_dir"]/"details.json"
    status = dict(path=str(path.relative_to(ROOT)), available=path.exists(), matches_protocol=False)
    if not path.exists():
        return status
    report = json.loads(path.read_text())
    run, metrics = report["run"], report["metric_summaries"]
    manifest = json.loads((ROOT/settings["manifest_path"]).read_text())
    complete = (len(report["questions"]) == manifest["case_count"]*settings["repetitions"]
                and set(metrics["trials"]) == {str(t) for t in range(1,settings["repetitions"]+1)})
    matches = (run["judge_protocol_sha256"] == judge_protocol(config)
               and run["dataset_sha256"] == digest(ROOT/settings["dataset_path"]) == manifest["dataset_sha256"]
               and run["manifest_sha256"] == digest(ROOT/settings["manifest_path"]))
    return {**status, "sha256":digest(path), "matches_protocol":matches, "complete":complete,
            "returned_models":run["returned_models"], "agreement":metrics["combined"]["exact_case_accuracy"]}


def write_reports(directory, run, questions, calibration):
    directory.mkdir(parents=True, exist_ok=True)
    metrics = summarize(questions)
    validation = run.get("judge_validation", {})
    lines = ["# Document QA: final-answer evaluation", "",
        "These are LLM judgments. Judge agreement and known limitations are reported separately, without a pass/fail qualification threshold.", "",
        "Fact coverage, grounding, contradictions, and abstention evaluate the generated answers. "
        "The saved context is used only as evidence for answer claims. No chunk precision or recall is calculated.", "",
        f"- Judge: Azure OpenAI `{run['judge_settings']['model_id']}`. Same model family as the answering model.",
        f"- Saved answer run: {run['source_run']['timestamp_utc']}, `{run['source_run']['model_id']}`, answer limit {run['source_run']['answer_max_new_tokens']} tokens.",
        f"- Saved input: `{run['input_path']}`, SHA-256 `{run['input_sha256']}`.",
        f"- Questions evaluated: {len(questions)}. No retrieval, reranking or answer generation was rerun.",
        f"- Synthetic calibration: {sum(case['passed'] for case in calibration['cases'])}/{len(calibration['cases'])} passed.", "",
        "| Metric | Macro average | Scored questions | N/A | Unscored |", "|---|---:|---:|---:|---:|"]
    for name, metric in metrics.items():
        score = f"{metric['average']:.1%}" if metric["average"] is not None else "N/A"
        lines.append(f"| {name.replace('_', ' ').capitalize()} | {score} | {metric['scored']} | {metric['not_applicable']} | {metric['unscored']} |")
    source = run["source_run"]
    if "ablation" in source:
        lines += ["", "## Evaluated answer-generation settings", "",
                  "These settings describe the saved answers, which may differ from the current configuration.", "",
                  f"- Dense / BM25 / query expansion: `{source['ablation']}`.",
                  f"- Dense index: `{source.get('dense_index_type')}`. Candidate limits: dense `{source.get('dense_top_k')}`, BM25 `{source.get('bm25_top_k')}`.",
                  f"- Chunk size / overlap: `{source.get('chunk_size')}` / `{source.get('chunk_overlap')}` characters.",
                  f"- Reranker: `{source.get('reranker_model')}`. Context limit: `{source.get('final_top_k')}` chunks.",
                  f"- Embeddings: `{source.get('embedding_model')}`.",
                  f"- Indexing mode: `{source.get('indexing_mode')}`."]
    if validation.get("available"):
        target = os.path.relpath(ROOT/validation["path"], directory).replace("details.json", "summary.md")
        lines += ["", f"[Judge performance on 48 cases]({target}): protocol match `{validation['matches_protocol']}`, full benchmark complete `{validation['complete']}`. "
                  "Expected labels are automatically source-audited, not human-approved. The benchmark contains 30 development and 18 reserved cases."]
    lines += ["", "Standalone citation rows are removed only for grounding. The judge separately lists abstention/context-insufficiency statements excluded from the claim denominator. "
              "Descriptions of technical content and guesses remain substantive claims. Original answers and exclusion records are retained in JSON. "
              "Coverage and abstention see the complete original answer."]
    lines += ["", "Fact coverage is covered required facts / all required facts. Missing/incomplete and contradicted facts receive zero coverage credit. "
        "Grounding is context-supported claims / extracted factual claims. Contradiction rates use the same denominators. "
        "Abstention accuracy is appropriate abstentions / validly judged unanswerable questions. "
        "Question scores are averaged equally, with N/A and unscored results excluded and counted above. "
        "Any uncertain label or exhausted validation failure makes that question's affected metric unscored. "
        "An answer without factual claims has N/A grounding, not a perfect grounding score.", "",
        "These are model estimates, not objective correctness or human approval. Fact coverage does not assess every extra claim. "
        "Unsupported does not necessarily mean false. Claim extraction and semantic judgments can be wrong, and using the same model family can introduce bias. "
        "Calibration checks simple synthetic cases, not benchmark accuracy. Literal quote validation establishes provenance, not entailment.", "",
        "## Per-question results", "", "| Question | Fact coverage | Grounding | Reference contradictions | Context contradictions | Abstention |", "|---|---:|---:|---:|---:|---|"]
    def cell(metric):
        return f"{metric['score']:.1%}" if metric["status"] == "scored" else metric["status"]
    for question in questions:
        scores = question_scores(question)
        abstention = question["judgments"]["abstention"]
        label = abstention["result"]["label"] if abstention.get("result") else abstention["status"]
        lines.append(f"| {question['id']} | " + " | ".join(cell(scores[name]) for name in
            ("fact_coverage", "grounding_rate", "reference_contradiction_rate", "context_contradiction_rate")) + f" | {label} |")
    unanswerable = [q for q in questions if q.get("answerability", {}).get("label")=="unanswerable_within_allowed_sources"]
    if unanswerable:
        lines += ["", "## Answers to unanswerable questions", ""]
        for q in unanswerable:
            lines += [f"### {q['id']}", "", q["question"], ""]
            lines += ["> " + line.rstrip() if line.strip() else ">" for line in q["generated_answer"].splitlines()]
            lines.append("")
    total_calls = sum(q["llm_calls"] for q in questions)
    tokens = Counter()
    for question in questions:
        tokens.update(question["token_usage"])
    lines += ["", f"Benchmark judging calls: {total_calls}. Recorded benchmark API tokens: `{dict(tokens)}`. "
              f"Calibration calls: {calibration['llm_calls']}, tokens: `{calibration['token_usage']}`. "
              "SDK retries may add requests not represented in call counts. Recorded usage is not an Azure bill.", "",
              "## Judge configuration", "", "```yaml", yaml.safe_dump(run["judge_settings"], sort_keys=False).rstrip(), "```", ""]
    details = dict(schema_version="1.1.0", evaluation_target="generated_answers", run=run, calibration=calibration, metric_summaries=metrics,
                   questions=[{**q, "metrics": question_scores(q)} for q in questions])
    # Stage all three files before replacing a completed report.
    with tempfile.TemporaryDirectory(dir=directory.parent, prefix=".answer-report-") as temporary:
        stage = Path(temporary)
        atomic_json(stage / "details.json", details)
        (stage / "summary.md").write_text("\n".join(lines), encoding="utf-8")
        with (stage / "per_question.csv").open("w", encoding="utf-8", newline="") as file:
            fields = ["question_id", "question", "generated_answer", "reference_answer"]
            fields += [name + suffix for name in metrics for suffix in ("_score", "_status", "_matched", "_total")]
            writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for q in questions:
                row = {key: q[key] for key in ("question", "generated_answer", "reference_answer")}
                # CSV is a display export. JSON retains the exact original answer.
                row["generated_answer"] = "\n".join(line.rstrip() for line in q["generated_answer"].split("\n"))
                row["question_id"] = q["id"]
                for name, metric in question_scores(q).items():
                    row.update({name + "_score": metric["score"], name + "_status": metric["status"],
                                name + "_matched": metric.get("matched"), name + "_total": metric.get("total")})
                writer.writerow(row)
        for name in ("summary.md", "details.json", "per_question.csv"):
            os.replace(stage / name, directory / name)
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--calibrate", action="store_true", help="Run only the five synthetic judge checks.")
    args = parser.parse_args(argv)
    if (args.limit is not None and args.limit < 1) or (args.resume and args.restart):
        parser.error("Use a positive limit and choose either --resume or --restart.")
    config = yaml.safe_load((ROOT / "config.yml").read_text())
    settings = config["qa_answer_evaluation"]
    for name in ("max_workers", "max_new_tokens", "timeout_seconds"):
        if type(settings[name]) is not int or settings[name] < 1:
            raise ValueError(f"qa_answer_evaluation.{name} must be a positive integer.")
    if type(settings["validation_retries"]) is not int or settings["validation_retries"] < 0:
        raise ValueError("validation_retries must be nonnegative.")
    input_path = ROOT / settings["input_path"]
    directory = ROOT / config["document_qa_evaluation"]["results_dir"]
    if input_path.resolve() == (directory/"details.json").resolve():
        raise ValueError("Saved predictions must use a separate input file so reports cannot overwrite them.")
    saved = json.loads(input_path.read_text())
    selected = saved["questions"][:args.limit] if args.limit else saved["questions"]
    if not selected or len({q["id"] for q in selected}) != len(selected):
        raise ValueError("Saved question IDs must be unique and nonempty.")
    # Compare against frozen references before spending API quota.
    dataset_path = ROOT / config["document_qa_evaluation"]["dataset_path"]
    references = {r["id"]:r for r in (json.loads(line) for line in dataset_path.read_text().splitlines() if line.strip())}
    for question in selected:
        reference = references[question["id"]]
        for saved_key, reference_key in (("question", "question"), ("reference_answer", "reference_answer"),
                ("required_facts", "atomic_required_facts"), ("reference_evidence", "evidence_records"),
                ("allowed_sources", "allowed_sources"), ("answerability", "answerability")):
            if question[saved_key] != reference.get(reference_key, []):
                raise ValueError(f"Saved input differs from the benchmark: {question['id']} {saved_key}")
    identity = dict(input_sha256=digest(input_path), dataset_sha256=digest(dataset_path),
                    code_sha256=digest(__file__), judge_settings=settings,
                    azure_settings={key:config["llm"]["azure"][key] for key in
                                    ("base_url", "api_key_env", "reasoning_effort", "max_retries")}, limit=args.limit)
    checkpoint_path = directory / ".checkpoint" / "answers.json"
    checkpoint = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() and not args.restart else None
    if checkpoint and not args.resume and not checkpoint.get("complete"):
        raise ValueError("Unfinished saved progress exists. Use --resume or --restart.")
    if args.resume and checkpoint and checkpoint["identity"] != identity:
        raise ValueError("Cannot resume: saved answers, code, configuration or selection changed.")
    if not args.resume or not checkpoint:
        checkpoint = dict(identity=identity, complete=False, questions={}, calibration=None)
    if not checkpoint["calibration"]:
        checkpoint["calibration"] = calibration_cases(AnswerJudge(config))
        atomic_json(checkpoint_path, checkpoint)
    if not checkpoint["calibration"]["passed"]:
        raise RuntimeError("Judge calibration failed. No benchmark judgments were run. Inspect the checkpoint.")
    if args.calibrate:
        return
    run = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), input_path=settings["input_path"],
               source_run=dict(saved["run"]), evaluation_target="generated_answers",
               **identity, judge_validation=validation_status(config))
    pending = [q for q in selected if q["id"] not in checkpoint["questions"]]
    print(f"Judging {len(pending)} saved answers, reusing {len(selected)-len(pending)}, workers={settings['max_workers']}.", flush=True)
    def work(question):
        print(f"Starting {question['id']}", flush=True)
        return evaluate_saved_answer(question, AnswerJudge(config))
    with ThreadPoolExecutor(max_workers=settings["max_workers"]) as pool:
        futures = {pool.submit(work, question):question["id"] for question in pending}
        for future in as_completed(futures):
            question_id = futures[future]
            checkpoint["questions"][question_id] = future.result()
            atomic_json(checkpoint_path, checkpoint)
            calls = sum(q["llm_calls"] for q in checkpoint["questions"].values())
            print(f"Finished {question_id}: {len(checkpoint['questions'])}/{len(selected)}, recorded calls={calls}", flush=True)
    questions = [checkpoint["questions"][q["id"]] for q in selected]
    returned_models = sorted({model for q in questions for model in q["judge_models"]})
    validation = run["judge_validation"]
    validation["matches_answer_model"] = validation.get("returned_models") == returned_models
    metrics = write_reports(directory, run, questions, checkpoint["calibration"])
    checkpoint["complete"] = True
    atomic_json(checkpoint_path, checkpoint)
    print(json.dumps(metrics, indent=2), flush=True)
    print(f"Saved {directory / 'summary.md'}", flush=True)


if __name__ == "__main__":
    main()
