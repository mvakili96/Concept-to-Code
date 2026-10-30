"""Evaluate the production related-problem workflow against frozen source labels."""
import argparse
import copy
import csv
import hashlib
import json
import logging
import os
import queue
import re
import statistics
import tempfile
import threading
import time
import unicodedata
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
from pathlib import Path

import pypdf
import yaml

ROOT = Path(__file__).resolve().parent
USEFUL = {"direct_match", "related_practice", "stretch_connection"}
LABELS = USEFUL | {"unrelated", "uncertain"}
OUTPUTS = ("summary.md", "per_question.csv", "details.json", "pending_review.jsonl")


def digest(path):
    with Path(path).open("rb") as file:
        result = hashlib.sha256()
        for block in iter(lambda: file.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def normalize(text):
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"(?<=\w)[-\u00ad\u2010]\s*\n\s*(?=\w)", "", text)
    return " ".join(text.split())


def json_read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def safe_metadata(value):
    """Keep configuration useful without serializing credentials or request headers."""
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if key.lower() in {
            "api_key", "password", "secret", "access_token", "authorization"
        } else safe_metadata(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [safe_metadata(item) for item in value]
    return value


class SourceCorpus:
    """Verify citations independently from extracted original PDFs, not RAG answers."""

    def __init__(self, root, documents, isolation):
        self.root, self.documents, self.isolation = Path(root), documents, isolation
        self.readers, self.pages, self.problems = {}, {}, {}
        self.lock = threading.RLock()

    def page(self, source, page):
        with self.lock:
            if source not in self.documents or type(page) is not int or page < 1:
                raise ValueError("Unknown PDF source or invalid physical page.")
            key = (source, page)
            if key not in self.pages:
                if source not in self.readers:
                    self.readers[source] = pypdf.PdfReader(self.root / self.documents[source]["relative_path"])
                reader = self.readers[source]
                if len(reader.pages) != self.documents[source]["pdf_pages"] or page > len(reader.pages):
                    raise ValueError("PDF page count differs from the benchmark manifest.")
                self.pages[key] = reader.pages[page - 1].extract_text() or ""
            return self.pages[key]

    def anchor(self, evidence):
        raw = self.page(evidence["source"], evidence["page"])
        start, end = evidence["start"], evidence["end_exclusive"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(raw):
            raise ValueError("Invalid reference passage offsets.")
        if raw[start:end] != evidence["quote"]:
            raise ValueError("Reference quote differs from its original PDF-page slice.")

    def problem(self, source, page, number):
        with self.lock:
            key = (source, page, number)
            if key not in self.problems:
                if type(number) is not int or number < 1:
                    raise ValueError("Invalid problem number.")
                raw = self.page(source, page)
                headings = list(re.finditer(self.isolation["header_pattern"], raw))
                footers = list(re.finditer(self.isolation["footer_pattern"], raw))
                matches = [i for i, heading in enumerate(headings) if int(heading["number"]) == number]
                if len(matches) != 1 or len(footers) != 1:
                    raise ValueError("Missing or ambiguous original problem boundaries.")
                index = matches[0]
                heading = headings[index]
                end = headings[index + 1].start() if index + 1 < len(headings) else footers[0].start()
                if end <= heading.end():
                    raise ValueError("Invalid original problem boundaries.")
                original = raw[heading.end():end]
                start = heading.end() + len(original) - len(original.lstrip())
                body = original.strip()
                self.problems[key] = dict(source=source, page=page, number=number,
                    title=" ".join(heading["title"].split()), difficulty=heading["difficulty"],
                    body_start=start, body_end_exclusive=start + len(body), body=body)
            return self.problems[key]

    def verify_chunk(self, chunk):
        raw = self.page(chunk["source"], chunk["page"])
        start, text = chunk["start_index"], chunk["text"]
        if type(start) is not int or start < 0 or not isinstance(text, str) or not text:
            raise ValueError("Invalid chunk text or offsets.")
        if raw[start:start + len(text)] != text:
            raise ValueError("Retrieved chunk differs from its original PDF-page slice.")

    def verify_recommendation(self, judgment, technical_chunks, question, leetcode_source):
        identity = judgment["problem_identity"]
        if judgment["source"] != leetcode_source:
            raise ValueError("Recommendation is outside the allowed LeetCode PDF.")
        original = self.problem(judgment["source"], judgment["page"], identity["number"])
        if any(identity.get(key) != original[key] for key in ("title", "difficulty")):
            raise ValueError("Recommended title/difficulty differs from the original heading.")
        expected_id = f"{original['source']}::page={original['page']}::problem={original['number']}"
        if judgment["problem_id"] != expected_id:
            raise ValueError("Recommended ID disagrees with its source identity.")
        pspan = judgment["problem_evidence_span"]
        self._span(original["body"], pspan, judgment["leetcode_quote"])
        constraints = re.search(r"(?im)^[\t ]*Constraints[.:]", original["body"])
        if constraints and pspan["end"] > constraints.start():
            raise ValueError("Selected coding evidence includes constraints instead of mechanism prose.")
        technical = judgment["technical_evidence"]
        if technical["source"] not in question["allowed_technical_sources"]:
            raise ValueError("Technical evidence violates the question's source restriction.")
        matches = [c for c in technical_chunks if c["chunk_id"] == technical["chunk_id"]]
        if len(matches) != 1:
            raise ValueError("Technical evidence has no unique retrieved passage.")
        chunk = matches[0]
        if (chunk["source"], chunk["page"]) != (technical["source"], technical["page"]):
            raise ValueError("Technical evidence citation disagrees with the retrieved passage.")
        self.verify_chunk(chunk)
        tspan = judgment["technical_evidence_span"]
        self._span(chunk["text"], tspan, judgment["technical_quote"])
        return original

    @staticmethod
    def _span(body, span, quote):
        start, end = span["start"], span["end"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(body):
            raise ValueError("Invalid selected quote offsets.")
        if not quote or body[start:end] != span["quote"] or span["quote"] != quote:
            raise ValueError("Selected quote is not the claimed consecutive source text.")


def load_benchmark(config, root=ROOT):
    settings = config["leetcode_recommendation_evaluation"]
    paths = {key: Path(root) / settings[key] for key in ("dataset_path", "references_path", "manifest_path")}
    questions = [json.loads(line) for line in paths["dataset_path"].read_text().splitlines() if line.strip()]
    references, manifest = json_read(paths["references_path"]), json_read(paths["manifest_path"])
    ids = [q["id"] for q in questions]
    if not ids or len(ids) != len(set(ids)) or any(not re.fullmatch(r"[A-Za-z0-9_-]+", qid) for qid in ids):
        raise ValueError("Benchmark question IDs must be unique, nonempty and filename-safe.")
    if references["schema_version"] != "1.0.0" or manifest["schema_version"] != "1.0.0":
        raise ValueError("Unsupported LeetCode benchmark schema.")
    if len(questions) != manifest["questions"] or len(references["topics"]) != manifest["topics"]:
        raise ValueError("Question/topic counts disagree with the manifest.")
    if len(references["pairs"]) != manifest["reviewed_pairs"]:
        raise ValueError("Reference pair count disagrees with the manifest.")
    for key in ("dataset_path", "references_path"):
        if digest(paths[key]) != manifest["data_sha256"][paths[key].name]:
            raise ValueError(f"Benchmark file hash mismatch: {paths[key].name}")
    documents = {doc["source"]: doc for doc in manifest["documents"]}
    if len(documents) != len(manifest["documents"]):
        raise ValueError("Duplicate corpus source names.")
    for doc in documents.values():
        if digest(Path(root) / doc["relative_path"]) != doc["sha256"]:
            raise ValueError(f"Original PDF hash mismatch: {doc['source']}")
    corpus = SourceCorpus(root, documents, config["related_problem"]["problem_isolation"])
    for question in questions:
        topic = references["topics"][question["topic_id"]]
        if question["schema_version"] != "1.0.0" or not question["question"].strip():
            raise ValueError("Invalid question schema or empty question.")
        if question["kind"] not in ("ordinary", "explicit_naming_control"):
            raise ValueError("Unknown benchmark question kind.")
        if question["allowed_technical_sources"] != topic["allowed_technical_sources"]:
            raise ValueError("Question/topic source restrictions disagree.")
        if not set(question["allowed_technical_sources"]) <= documents.keys():
            raise ValueError("Question references an unknown source.")
        if (question["kind"] == "explicit_naming_control") != bool(topic.get("control")):
            raise ValueError("Question/control annotation disagrees with its topic.")
    for topic in references["topics"].values():
        for evidence in topic["technical_evidence"]:
            corpus.anchor(evidence)
            if evidence["source"] not in topic["allowed_technical_sources"]:
                raise ValueError("Reference technical evidence is outside its topic's sources.")
    for key, pair in references["pairs"].items():
        if key != f"{pair['topic_id']}::lc{pair['number']}" or pair["label"] not in LABELS:
            raise ValueError("Invalid pair identity or relevance label.")
        if pair["source"] != config["related_problem"]["source"]:
            raise ValueError("Reference problem is outside the LeetCode source.")
        topic = references["topics"][pair["topic_id"]]
        if not pair["technical_evidence_ids"] or not set(pair["technical_evidence_ids"]) <= {e["id"] for e in topic["technical_evidence"]}:
            raise ValueError("Invalid reference technical-evidence links.")
        if pair.get("review_status") != "source_audited" or not pair.get("review_method"):
            raise ValueError("Reference pair has not passed its source audit.")
        if not pair["rationale"].strip() or not pair["limitation"].strip():
            raise ValueError("Reference pair needs a rationale and limitation.")
        original = corpus.problem(pair["source"], pair["page"], pair["number"])
        if any(pair[key] != original[key] for key in ("title", "difficulty", "body_start", "body_end_exclusive")):
            raise ValueError("Reference problem identity/body bounds differ from the PDF.")
        corpus.anchor(pair["problem_evidence"])
        anchor = pair["problem_evidence"]
        if (anchor["source"], anchor["page"]) != (pair["source"], pair["page"]):
            raise ValueError("Reference problem evidence disagrees with its source identity.")
        if not original["body_start"] <= anchor["start"] < anchor["end_exclusive"] <= original["body_end_exclusive"]:
            raise ValueError("Reference problem quote is outside its statement body.")
    for topic_id, topic in references["topics"].items():
        for number in topic["target_problem_numbers"]:
            if references["pairs"].get(f"{topic_id}::lc{number}", {}).get("label") not in USEFUL:
                raise ValueError("A positive target lacks a useful reviewed reference pair.")
    return questions, references, manifest, corpus


def compact_output(output, chunk_lookup):
    """Preserve useful stages without copying every statement and model prompt."""
    result = {key: output[key] for key in (
        "workflow", "technical_selected_sources", "leetcode_selected_sources", "query_expansion",
        "technical_retrieval_query", "technical_chunks", "pattern_extraction", "leetcode_search_query",
        "leetcode_query_plan", "searched_pattern_indices", "leetcode_retrieval_runs", "leetcode_shortlist",
        "recommendation_validation", "generated_answer", "related_problem_method", "grounded_answer", "batched_selection", "title_selection"
    ) if key in output}
    result["leetcode_candidates"] = []
    for item in output.get("leetcode_candidates", []):
        bounds = chunk_lookup.get(item["chunk_id"], {})
        result["leetcode_candidates"].append({**item, **{key: bounds[key] for key in (
            "start_index", "end_exclusive") if key in bounds}})
    result["leetcode_chunks"] = [{key: item[key] for key in (
        "problem_id", "problem_identity", "source", "page", "problem_spans", "retrieved_problem_spans",
        "parent_chunk_ids", "connection_level", "chunk_cross_encoder_score", "problem_cross_encoder_score"
    ) if key in item} for item in output.get("leetcode_chunks", [])]
    result["conceptual_judgments"] = []
    for item in output.get("conceptual_judgments", []):
        judgment = {key: item[key] for key in (
            "problem_id", "problem_identity", "source", "page", "status", "match_label", "connection_level",
            "selected_for_context", "problem_operation", "technical_operation", "shared_mechanism",
            "technical_evidence", "technical_evidence_span", "problem_evidence_span", "technical_quote", "leetcode_quote",
            "important_difference", "problem_cross_encoder_score", "note"
        ) if key in item}
        verification = item.get("verification", {})
        judgment["verification"] = {key: value for key, value in verification.items() if key != "attempts"}
        judgment["attempt_counts"] = {"extraction": len(item.get("attempts", [])), "comparison": len(verification.get("attempts", []))}
        judgment["validation_errors"] = [attempt["error"] for attempts in (
            item.get("attempts", []), verification.get("attempts", [])
        ) for attempt in attempts if attempt.get("error")]
        result["conceptual_judgments"].append(judgment)
    return result


def stage_coverage(question, output, references):
    target_numbers = references["topics"][question["topic_id"]]["target_problem_numbers"]
    targets = [pair for pair in references["pairs"].values()
               if pair["topic_id"] == question["topic_id"] and pair["number"] in target_numbers]
    result = {}
    if output.get("related_problem_method") in ("batched", "titles"):
        titles = output["related_problem_method"] == "titles"
        info = output["title_selection" if titles else "batched_selection"]
        runs = info.get("batches", [])
        presented = info["presented_problem_numbers"] if titles else [number for run in runs for number in run["presented_problem_numbers"]]
        complete = (info["status"] == "completed" and len(presented) == info["total_problems"]
                    and set(presented) == set(range(1, info["total_problems"] + 1)))
        status = "not_applicable" if info["status"] == "skipped_no_technical_evidence" else "scored" if complete else "unscored"
        pool = set(info["shortlisted_problem_numbers"]) if titles else set(
            runs[-1]["presented_problem_numbers"] + runs[-1]["carried_problem_numbers"]) if runs else set()
        stages = (("all_titles_presented", set(presented)), ("shortlisted_statements_presented", pool)) if titles else (
            ("all_problems_presented", set(presented)), ("final_selection_pool", pool))
        for name, numbers in stages:
            result[name] = dict(status=status, matched_target_ids=[p["pair_id"] for p in targets
                                if p["source"] == info["source"] and p["number"] in numbers] if complete else [],
                                total_targets=len(targets), mapping_failures=[] if complete or status == "not_applicable"
                                else ["Catalogue presentation could not be verified."])
        for name in ("merged_candidates", "chunk_shortlist", "final_context"):
            result[name] = dict(status="not_applicable", matched_target_ids=[], total_targets=len(targets), mapping_failures=[])
        identifiers = set(output.get("recommendation_validation", {}).get("accepted_problem_ids", []))
        result["recommendations"] = dict(status="scored", matched_target_ids=[p["pair_id"] for p in targets
            if f"{p['source']}::page={p['page']}::problem={p['number']}" in identifiers], total_targets=len(targets), mapping_failures=[])
        return result
    for name, chunks in (("merged_candidates", output.get("leetcode_candidates", [])),
                         ("chunk_shortlist", output.get("leetcode_shortlist", []))):
        failures = [c.get("chunk_id") for c in chunks if type(c.get("start_index")) is not int
                    or ("end_exclusive" in c and type(c["end_exclusive"]) is not int)
                    or ("end_exclusive" not in c and not isinstance(c.get("text"), str))]
        hits = []
        for pair in targets if not failures else []:
            for chunk in chunks:
                end = chunk.get("end_exclusive", chunk.get("start_index", 0) + len(chunk.get("text", "")))
                if (chunk.get("source"), chunk.get("page")) == (pair["source"], pair["page"]) and not failures:
                    if max(chunk["start_index"], pair["body_start"]) < min(end, pair["body_end_exclusive"]):
                        hits.append(pair["pair_id"])
                        break
        result[name] = dict(status="unscored" if failures else "scored", matched_target_ids=hits,
                            total_targets=len(targets), mapping_failures=failures)
    for name, identifiers in (
        ("final_context", {c["problem_id"] for c in output.get("leetcode_chunks", [])}),
        ("recommendations", set(output.get("recommendation_validation", {}).get("accepted_problem_ids", []))),
    ):
        hits = [p["pair_id"] for p in targets if f"{p['source']}::page={p['page']}::problem={p['number']}" in identifiers]
        result[name] = dict(status="scored", matched_target_ids=hits, total_targets=len(targets), mapping_failures=[])
    return result


def score_question(question, output, references, corpus, leetcode_source):
    judgments = {}
    for item in output.get("conceptual_judgments", []):
        judgments.setdefault(item.get("problem_id"), []).append(item)
    selected = output.get("recommendation_validation", {}).get("accepted_problem_ids", [])
    items, seen, duplicate_ids = [], set(), []
    for identifier in selected:
        if identifier in seen:
            duplicate_ids.append(identifier)
            continue
        seen.add(identifier)
        item = dict(problem_id=identifier, label="unscored", status="unscored")
        try:
            candidates = judgments.get(identifier, [])
            if len(candidates) != 1:
                raise ValueError("Selected problem has no unique judgment record.")
            judgment = candidates[0]
            original = corpus.verify_recommendation(judgment, output.get("technical_chunks", []), question, leetcode_source)
            key = f"{question['topic_id']}::lc{original['number']}"
            reference = references["pairs"].get(key)
            if reference and (reference["source"], reference["page"], reference["title"]) != (
                    original["source"], original["page"], original["title"]):
                raise ValueError("Selected identity disagrees with the reference pair.")
            item.update(status="verified", label=reference["label"] if reference else "unassessed",
                        pair_id=key, number=original["number"], title=original["title"], difficulty=original["difficulty"],
                        source=original["source"], page=original["page"], displayed_level=judgment.get("connection_level"),
                        technical_quote=judgment["technical_quote"], problem_quote=judgment["leetcode_quote"],
                        technical_evidence=judgment["technical_evidence"],
                        rationale=reference["rationale"] if reference else None,
                        limitation=reference["limitation"] if reference else None)
            chunk = next(c for c in output["technical_chunks"] if c["chunk_id"] == judgment["technical_evidence"]["chunk_id"])
            for role, span, base, source, page in (
                ("problem_evidence", judgment["problem_evidence_span"], original["body_start"], original["source"], original["page"]),
                ("technical_passage", judgment["technical_evidence_span"], chunk["start_index"], chunk["source"], chunk["page"]),
            ):
                item[role] = dict(source=source, page=page, start=base + span["start"],
                                  end_exclusive=base + span["end"], quote=span["quote"])
        except (ValueError, KeyError, TypeError, IndexError) as error:
            item["mapping_error"] = str(error)
        items.append(item)
    counts = Counter(item["label"] for item in items)
    useful = sum(counts[label] for label in USEFUL)
    scored = useful + counts["unrelated"]
    unresolved = sum(counts[label] for label in ("uncertain", "unassessed", "unscored"))
    return dict(items=items, duplicate_ids=duplicate_ids, label_counts=dict(counts), useful_items=useful,
                scored_items=scored, useful_over_scored=useful / scored if scored else None,
                has_useful=useful > 0, possibly_useful=bool(useful or unresolved),
                abstained=not selected, control_conformant=(not selected if question["kind"] == "explicit_naming_control" else None),
                usefulness_bounds=[useful / len(items), (useful + unresolved) / len(items)] if items else None,
                labeled_items=sum(counts[label] for label in LABELS), total_items=len(items),
                stage_coverage=stage_coverage(question, output, references))


def percentile(values, p):
    values = sorted(values)
    index = (len(values) - 1) * p
    lo = int(index)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)


def summarize(records):
    completed = [r for r in records if r["status"] == "completed"]
    ordinary = [r for r in completed if r["kind"] == "ordinary"]
    controls = [r for r in completed if r["kind"] == "explicit_naming_control"]
    counts = Counter()
    for record in completed:
        counts.update(record["assessment"]["label_counts"])
    useful = sum(counts[label] for label in USEFUL)
    scored, total = useful + counts["unrelated"], sum(counts.values())
    unresolved = sum(counts[label] for label in ("uncertain", "unassessed", "unscored"))
    times = [r["seconds"] for r in records]
    tokens = Counter()
    for record in records:
        tokens.update(record.get("telemetry", {}).get("token_usage") or {})
    return dict(evaluated_questions=len(records), completed_questions=len(completed),
        failed_executions=len(records) - len(completed), ordinary_questions=len(ordinary),
        attempted_ordinary_questions=sum(r["kind"] == "ordinary" for r in records),
        useful_ordinary_questions=sum(r["assessment"]["has_useful"] for r in ordinary),
        useful_ordinary_upper=sum(r["assessment"]["possibly_useful"] for r in ordinary),
        ordinary_abstentions=sum(r["assessment"]["abstained"] for r in ordinary),
        controls=len(controls), conformant_controls=sum(r["assessment"]["control_conformant"] for r in controls),
        recommendations=total, label_counts=dict(counts), useful_items=useful, scored_items=scored,
        useful_over_scored=useful / scored if scored else None,
        label_coverage=sum(counts[label] for label in LABELS) / total if total else None,
        usefulness_bounds=[useful / total, (useful + unresolved) / total] if total else None,
        latency_seconds=dict(mean=statistics.mean(times), median=statistics.median(times), p95=percentile(times, .95)) if times else None,
        llm_calls=sum(r.get("telemetry", {}).get("llm_calls", 0) for r in records),
        token_usage=dict(tokens) if any(r.get("telemetry", {}).get("token_usage") is not None for r in records) else None,
        pattern_fallbacks=sum(r.get("output", {}).get("pattern_extraction", {}).get("status") == "fallback" for r in completed),
        unscored_candidate_judgments=sum(j.get("status", "").startswith("unscored") for r in completed
            for j in r.get("output", {}).get("conceptual_judgments", [])))


def build_summary(run, records, metrics):
    counts = metrics["label_counts"]
    method = run["config"]["related_problem"].get("method", "retrieval")
    batched = method in ("batched", "titles")
    def fraction(numerator, denominator):
        return f"{numerator}/{denominator}" if denominator else "N/A"
    def percentage(numerator, denominator):
        return f"{numerator}/{denominator} ({numerator / denominator:.1%})" if denominator else "N/A"
    target_records = [r for r in records if r["status"] == "completed" and r["kind"] == "ordinary"
                      and r["assessment"]["stage_coverage"]["recommendations"]["total_targets"]]
    scored_targets = [r["assessment"]["stage_coverage"]["recommendations"] for r in target_records
                      if r["assessment"]["stage_coverage"]["recommendations"]["status"] == "scored"
                      and not r["assessment"]["label_counts"].get("unscored", 0)]
    matched_targets = sum(len(set(item["matched_target_ids"])) for item in scored_targets)
    total_targets = sum(item["total_targets"] for item in scored_targets)
    labeled_items = sum(counts.get(label, 0) for label in LABELS)
    lines = ["# LeetCode recommendation evaluation", "",
        "Fixed source-grounded development benchmark; labels are incomplete and include useful stretch practice. "
        "This is not held-out generalization or a score of answer correctness/faithfulness.", "",
        f"- Run ID: `{run['run_id']}`; origin: `{run['origin']}`",
        f"- Timestamp (UTC): {run['timestamp_utc']}",
        f"- Coverage: {'full benchmark' if run['full_dataset'] else 'subset'}; {len(records)}/{run['eligible_questions']} questions",
        f"- Model/provider: `{run['config']['llm']['model_id']}` / `{run['config']['llm'].get('provider', 'local')}`",
        f"- Benchmark files: `{run.get('benchmark_paths', {})}`",
        f"- Requested/effective workers: {run['requested_workers']} / {run['effective_workers']}",
        f"- Initial indexing mode: `{run.get('initial_indexing_mode', 'not recorded')}`; worker modes: `{run.get('effective_indexing_modes', [])}`",
        f"- Failed executions: {metrics['failed_executions']} (not abstentions)", "",
        "| Metric | Result |", "|---|---:|",
        f"| Assessed precision | {percentage(metrics['useful_items'], metrics['scored_items'])} |",
        f"| Hit rate | {percentage(metrics['useful_ordinary_questions'], metrics['ordinary_questions'])} |",
        f"| Annotated-target recall (micro) | {percentage(matched_targets, total_targets)} |",
        f"| Label coverage | {percentage(labeled_items, metrics['recommendations'])} |", "",
        "Relevant means a frozen reference label of direct match, related practice, or stretch connection. "
        "Assessed precision excludes uncertain, unassessed and invalidly mapped recommendations. "
        "Hit rate is the fraction of completed ordinary questions with at least one relevant recommendation. "
        "Label coverage includes uncertain labels and does not mean every recommendation has a definitive relevance judgment.", "",
        "Annotated-target recall counts original positive targets actually recommended, summed across questions "
        "(micro averaging). Targets count once within a question and again for another wording. "
        "These targets are incomplete; this is not exhaustive semantic recall or document-QA evidence-text recall. "
        f"Scored target-bearing ordinary questions: {len(scored_targets)}/{len(target_records)}; "
        f"mapping-unscored: {len(target_records) - len(scored_targets)}. Questions without annotated targets are excluded.", "",
        "## Supporting diagnostics", "",
        "| Diagnostic | Result |", "|---|---:|",
        f"| Hit-rate upper bound, including unresolved outputs | {percentage(metrics['useful_ordinary_upper'], metrics['ordinary_questions'])} |",
        f"| All unique returned recommendations | {metrics['recommendations']} |",
        f"| Direct / related / stretch | {' / '.join(str(counts.get(k, 0)) for k in ('direct_match', 'related_practice', 'stretch_connection'))} |",
        f"| Unrelated / uncertain / unassessed / mapping-unscored | {' / '.join(str(counts.get(k, 0)) for k in ('unrelated', 'uncertain', 'unassessed', 'unscored'))} |",
        f"| Ordinary abstention rate | {percentage(metrics['ordinary_abstentions'], metrics['ordinary_questions'])} |",
        f"| Naming controls conforming (abstaining) | {fraction(metrics['conformant_controls'], metrics['controls'])} |",
        f"| Invalid candidate judgments after retries | {metrics['unscored_candidate_judgments'] if not batched else f'N/A ({method} selection)'} |",
        f"| Pattern-extraction fallbacks | {metrics['pattern_fallbacks'] if not batched else f'N/A ({method} selection)'} |",
        f"| LLM calls | {metrics['llm_calls']} |", ""]
    if metrics["label_coverage"] is not None:
        lines += [f"Relevance-precision lower/upper bounds over all returns: "
                  f"{metrics['usefulness_bounds'][0]:.1%}–{metrics['usefulness_bounds'][1]:.1%}. "
                  "These are incomplete-label bounds, not confidence intervals.", ""]
    if metrics["latency_seconds"]:
        lines += ["Mean / median / p95 question seconds: " + " / ".join(
            f"{metrics['latency_seconds'][key]:.1f}" for key in ("mean", "median", "p95")) + ". "
            "Initialization is excluded; first-use loading, concurrency and network delay can affect timings.", ""]
    lines += [f"Recorded API tokens: `{metrics['token_usage']}`. Local token usage is N/A. "
              "SDK retries or interrupted in-flight calls may not be represented in recorded usage; this is not an Azure bill.", "",
              "## Pipeline settings", "", "```yaml", yaml.safe_dump(run["config"], sort_keys=False).rstrip(), "```", "",
              "## Annotated-target overlap", "",
              "Secondary diagnostics use the original positive targets, not an exhaustive relevance catalog. "
              "Any source-body overlap counts at chunk stages; it need not contain sufficient explanatory prose.", "",
              "| Stage | Questions with a target hit / scored eligible questions | Mapping-unscored questions |",
              "|---|---:|---:|"]
    stages = ("all_titles_presented", "shortlisted_statements_presented", "recommendations") if method == "titles" else (
        "all_problems_presented", "final_selection_pool", "recommendations") if batched else (
        "merged_candidates", "chunk_shortlist", "final_context", "recommendations")
    for stage in stages:
        eligible = [r["assessment"]["stage_coverage"][stage] for r in records if r["status"] == "completed"
                    and r["kind"] == "ordinary" and r["assessment"]["stage_coverage"][stage]["total_targets"]
                    and r["assessment"]["stage_coverage"][stage]["status"] != "not_applicable"]
        scored = [item for item in eligible if item["status"] == "scored"]
        lines.append(f"| {stage} | {fraction(sum(bool(item['matched_target_ids']) for item in scored), len(scored))} | {len(eligible) - len(scored)} |")
    if batched:
        description = ("Title selection presents every number/title, then only shortlisted full statements. "
                       if method == "titles" else "Batched selection presents every complete statement, carrying a shortlist between calls. ")
        lines += ["", description + "These are presentation/pool diagnostics, not semantic retrieval recall; "
                  "dense/BM25 and cross-encoder stages do not apply. "
                  "Python checks selected identities and literal evidence spans; semantic relevance is the selection model's judgment.", ""]
    lines += ["", "## Per-question results", "", "D=direct, R=related, S=stretch, X=unrelated, ?=uncertain, U=unassessed, !=mapping-unscored.", "",
              "| Question ID | Status | Recommended problems (reference labels) | Seconds |", "|---|---|---|---:|"]
    labels = dict(direct_match="D", related_practice="R", stretch_connection="S", unrelated="X", uncertain="?", unassessed="U", unscored="!")
    for record in records:
        items = record.get("assessment", {}).get("items", [])
        description = ", ".join(f"{item.get('number', item['problem_id'])} ({labels[item['label']]})" for item in items)
        if record["status"] == "failed":
            description = "execution failed (unscored)"
        lines.append(f"| {record['id']} | {record['status']} | {description or 'abstain'} | {record['seconds']:.1f} |")
    lines += ["", "Uncertain, unseen and invalidly mapped items are never automatically wrong. Failed questions "
              "are excluded from completed-question denominators and remain visible above. Predictions are scored "
              "by verified identity and frozen labels, not by the production judge's own grade. Source occurrence "
              "does not guarantee a generated explanation is supported. PDFs and indexes are not distributed.", ""]
    if run.get("provenance_note"):
        lines += ["## Run provenance", "", run["provenance_note"], ""]
    return "\n".join(lines)


def write_reports(results_dir, run, records):
    results_dir = Path(results_dir)
    results_dir.parent.mkdir(parents=True, exist_ok=True)
    metrics = summarize(records)
    pending = [{"question_id": r["id"], "topic_id": r["topic_id"], "question": r["question"],
                **item, "review_status": "unassessed"}
               for r in records for item in r.get("assessment", {}).get("items", []) if item["label"] == "unassessed"]
    details = dict(schema_version="1.0.0", run=run, metrics=metrics, questions=records)
    with tempfile.TemporaryDirectory(prefix=".leetcode-report-", dir=results_dir.parent) as directory:
        stage = Path(directory)
        (stage / "summary.md").write_text(build_summary(run, records, metrics), encoding="utf-8")
        (stage / "details.json").write_text(json.dumps(details, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (stage / "pending_review.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in pending), encoding="utf-8")
        fields = ["run_id", "question_id", "question", "kind", "status", "recommendations", "reference_labels", "useful_items",
                  "scored_items", "useful_over_scored", "unassessed_items", "uncertain_items", "mapping_unscored_items",
                  "abstained", "control_conformant", "seconds", "llm_calls", "generated_answer", "error"]
        with (stage / "per_question.csv").open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for record in records:
                assessment = record.get("assessment", {})
                items, counts = assessment.get("items", []), assessment.get("label_counts", {})
                writer.writerow(dict(run_id=run["run_id"], question_id=record["id"], question=record["question"], kind=record["kind"],
                    status=record["status"], recommendations=";".join(str(i.get("number", i["problem_id"])) for i in items),
                    reference_labels=";".join(i["label"] for i in items), useful_items=assessment.get("useful_items"),
                    scored_items=assessment.get("scored_items"), useful_over_scored=assessment.get("useful_over_scored"),
                    unassessed_items=counts.get("unassessed", 0), uncertain_items=counts.get("uncertain", 0),
                    mapping_unscored_items=counts.get("unscored", 0), abstained=assessment.get("abstained"),
                    control_conformant=assessment.get("control_conformant"), seconds=record["seconds"],
                    llm_calls=record.get("telemetry", {}).get("llm_calls", 0),
                    generated_answer=record.get("output", {}).get("generated_answer", ""), error=record.get("error", "")))
        # Prepare every output first. Retain rollback copies if replacement fails.
        results_dir.mkdir(parents=True, exist_ok=True)
        backups = {name: (results_dir / name).read_bytes() if (results_dir / name).exists() else None for name in OUTPUTS}
        replaced = []
        try:
            for name in OUTPUTS:
                os.replace(stage / name, results_dir / name)
                replaced.append(name)
        except Exception:
            for name in replaced:
                if backups[name] is None:
                    (results_dir / name).unlink()
                else:
                    (stage / name).write_bytes(backups[name])
                    os.replace(stage / name, results_dir / name)
            raise
    return metrics


class MeasuredLLM:
    """Observe usage only; never change prompts, generation options or replies."""

    def __init__(self, inner, provider):
        self.inner, self.provider = inner, provider
        self.lock = threading.Lock()
        self.reset()
        if provider == "azure_openai":
            original = inner.client.chat.completions.create

            def create(**kwargs):
                response = original(**kwargs)
                with self.lock:
                    self.models.add(response.model)
                    self.finishes[response.choices[0].finish_reason] += 1
                    if response.usage:
                        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                            self.tokens[key] += getattr(response.usage, key, 0)
                return response
            inner.client.chat.completions.create = create

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def reset(self):
        with self.lock:
            self.calls, self.tokens, self.models, self.finishes = 0, Counter(), set(), Counter()

    def invoke(self, *args, **kwargs):
        with self.lock:
            self.calls += 1
        return self.inner.invoke(*args, **kwargs)

    def snapshot(self):
        with self.lock:
            return dict(llm_calls=self.calls, token_usage=dict(self.tokens) if self.provider == "azure_openai" else None,
                        response_models=sorted(self.models), finish_reasons=dict(self.finishes))


def initialize_workers(config, count, corpus, pipeline_factory, resume=False):
    workers = []
    expected_sources = set(corpus.documents)
    for index in range(count):
        worker_config = copy.deepcopy(config)
        if index or resume:
            worker_config["indexing"]["mode"] = "load"
        paths = sorted(ROOT.glob(config["documents"]["pdf_glob"])) if worker_config["indexing"]["mode"] == "build" else []
        if worker_config["indexing"]["mode"] == "build" and {p.name for p in paths} != expected_sources:
            raise ValueError("Build corpus differs from the benchmark manifest.")
        pipeline = pipeline_factory(worker_config, paths)
        if set(pipeline.available_sources) != expected_sources:
            raise ValueError("Persisted corpus sources differ from the benchmark manifest.")
        for key, text in corpus.pages.items():
            if pipeline.page_texts.get(key) != text:
                raise ValueError(f"Stale indexed reference page: {key}. Rebuild the indexes.")
        pipeline.llm = MeasuredLLM(pipeline.llm, config["llm"].get("provider", "local"))
        lookup = {c.metadata["chunk_id"]: dict(start_index=c.metadata["start_index"],
                  end_exclusive=c.metadata["start_index"] + len(c.page_content)) for c in pipeline.chunks}
        workers.append(dict(pipeline=pipeline, chunk_lookup=lookup, active=None))
    return workers


def input_fingerprints(config, questions, root=None):
    root = ROOT if root is None else Path(root)
    normalized = copy.deepcopy(config)
    normalized["indexing"].pop("mode", None)  # Resume reuses artifacts; it never rebuilds.
    files = {name: digest(Path(root) / config["leetcode_recommendation_evaluation"][key]) for name, key in (
        ("questions", "dataset_path"), ("references", "references_path"), ("manifest", "manifest_path"))}
    files.update({name: digest(Path(root) / name) for name in ("main.py", "evaluate_leetcode_recommendation.py")})
    manifest = json_read(Path(root) / config["leetcode_recommendation_evaluation"]["manifest_path"])
    corpus = {doc["source"]: digest(Path(root) / doc["relative_path"]) for doc in manifest["documents"]}
    return dict(config_sha256=hashlib.sha256(json.dumps(safe_metadata(normalized), sort_keys=True).encode()).hexdigest(),
                files=files, corpus=corpus, selected_ids=[q["id"] for q in questions])


def index_fingerprints(config):
    directory = ROOT / config["indexing"]["persist_directory"]
    files = sorted(p for p in directory.rglob("*") if p.is_file())
    if not files:
        raise ValueError("No persisted index artifacts are available.")
    return {str(path.relative_to(directory)): digest(path) for path in files}


def open_checkpoint(directory, fingerprints, resume=False, restart=False):
    directory = Path(directory)
    metadata = directory / "run.json"
    old = json_read(metadata) if metadata.exists() else None
    if resume:
        if old is None:
            raise ValueError("No checkpoint exists. Start a new evaluation first.")
        if old["fingerprints"] != fingerprints:
            raise ValueError("Checkpoint inputs/configuration/code changed; use --restart for a new run.")
        return old
    if old and old["status"] != "completed" and not restart:
        raise ValueError("An unfinished checkpoint exists. Use --resume or explicitly --restart.")
    state = dict(schema_version="1.0.0", run_id=uuid.uuid4().hex, status="initializing", fingerprints=fingerprints,
                 timestamp_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(metadata, state)
    return state


def saved_records(directory, state):
    result = {}
    for identifier in state["fingerprints"]["selected_ids"]:
        path = Path(directory) / (identifier + ".json")
        if path.exists():
            record = json_read(path)
            if record.get("run_id") == state["run_id"]:
                if record["id"] != identifier or record["status"] not in ("completed", "failed"):
                    raise ValueError("Invalid checkpoint question record.")
                result[identifier] = record
    return result


def run_questions(questions, workers, references, corpus, leetcode_source, checkpoint_dir, run_id, records):
    available = queue.Queue()
    for worker in workers:
        available.put(worker)

    def execute(question):
        worker = available.get()
        pipeline = worker["pipeline"]
        pipeline.llm.reset()
        worker["active"] = question["id"]
        record = dict(run_id=run_id, id=question["id"], topic_id=question["topic_id"], question=question["question"],
                      kind=question["kind"], wording=question["wording"], status="completed")
        started = time.monotonic()
        try:
            output = pipeline.run_related_problem(question["question"])
            record["output"] = compact_output(output, worker["chunk_lookup"])
            record["assessment"] = score_question(question, record["output"], references, corpus, leetcode_source)
        except Exception as error:
            # Preserve a failed execution without turning it into an abstention.
            message = str(error)
            env_name = pipeline.config.get("llm", {}).get("azure", {}).get("api_key_env", "AZURE_OPENAI_API_KEY")
            secret = os.environ.get(env_name)
            if secret:
                message = message.replace(secret, "[REDACTED]")
            record.update(status="failed", error=f"{type(error).__name__}: {message}")
        finally:
            record.update(seconds=time.monotonic() - started, telemetry=pipeline.llm.snapshot())
            worker["active"] = None
            available.put(worker)
        return record

    remaining = [q for q in questions if q["id"] not in records]
    with ThreadPoolExecutor(max_workers=len(workers)) as executor:
        futures = {executor.submit(execute, question) for question in remaining}
        while futures:
            done, futures = wait(futures, timeout=10, return_when=FIRST_COMPLETED)
            for future in done:
                record = future.result()
                atomic_json(Path(checkpoint_dir) / (record["id"] + ".json"), record)
                records[record["id"]] = record
                print(f"[{len(records)}/{len(questions)}] {record['id']}: {record['status']}, "
                      f"{record['seconds']:.1f}s, {record['telemetry']['llm_calls']} LLM calls", flush=True)
            if not done:
                active = [f"{w['active']} ({w['pipeline'].llm.snapshot()['llm_calls']} calls)" for w in workers if w["active"]]
                print(f"[{len(records)}/{len(questions)} completed] Active: {', '.join(active)}", flush=True)
    return [records[q["id"]] for q in questions]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Evaluate the first N questions, not N topics.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--resume", action="store_true", help="Reuse compatible saved questions, including failures.")
    mode.add_argument("--restart", action="store_true", help="Explicitly replace unfinished checkpoint state for a fresh run.")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    return args


def main(argv=None, pipeline_factory=None):
    args = parse_args(argv)
    config = yaml.safe_load((ROOT / "config.yml").read_text())
    settings = config["leetcode_recommendation_evaluation"]
    requested = settings["max_workers"]
    if type(requested) is not int or requested < 1:
        raise ValueError("leetcode_recommendation_evaluation.max_workers must be a positive integer.")
    print("Verifying benchmark references and original PDFs before inference...", flush=True)
    questions, references, manifest, corpus = load_benchmark(config)
    selected = questions[:args.limit] if args.limit is not None else questions
    effective = min(requested, len(selected)) if config["llm"].get("provider", "local") == "azure_openai" else 1
    results_dir = ROOT / settings["results_dir"]
    checkpoint_dir = results_dir / ".checkpoint"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    # Prevent two processes from issuing paid requests for the same checkpoint.
    import fcntl
    with (checkpoint_dir / "lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Another evaluation owns this results checkpoint.") from error
        fingerprints = input_fingerprints(config, selected)
        state = open_checkpoint(checkpoint_dir, fingerprints, args.resume, args.restart)
        state.setdefault("initial_indexing_mode", config["indexing"]["mode"])
        if args.resume:
            if "indexes" not in state or index_fingerprints(config) != state["indexes"]:
                raise ValueError("Checkpoint index artifacts are missing or changed; start a fresh run.")
        records = saved_records(checkpoint_dir, state)
        if args.resume:
            print(f"Resume: {len(records)} saved question records, {len(selected) - len(records)} unfinished. "
                  "Saved failures are retained.", flush=True)
        run = dict(run_id=state["run_id"], timestamp_utc=state["timestamp_utc"], origin="live_production_workflow",
                   config=safe_metadata(config), full_dataset=len(selected) == len(questions), eligible_questions=len(questions),
                   requested_workers=requested, effective_workers=effective, fingerprints=fingerprints,
                   benchmark_version=manifest["benchmark_version"],
                   benchmark_paths={key: settings[key] for key in ("dataset_path", "references_path", "manifest_path")},
                   initial_indexing_mode=state["initial_indexing_mode"],
                   effective_indexing_modes=["load" if args.resume or index else config["indexing"]["mode"] for index in range(effective)],
                   resumed=args.resume, saved_questions_reused=len(records), new_questions_executed=len(selected) - len(records))
        workers = []
        try:
            if len(records) < len(selected):
                if pipeline_factory is None:
                    from main import RAGPipeline
                    pipeline_factory = RAGPipeline
                workers = initialize_workers(config, effective, corpus, pipeline_factory, resume=args.resume)
                state.update(indexes=index_fingerprints(config), status="running")
                atomic_json(checkpoint_dir / "run.json", state)
                print(f"Evaluating {len(selected)} questions with {effective} worker(s); {len(records)} already saved. "
                      "Each question can make dozens of LLM calls.", flush=True)
                records_list = run_questions(selected, workers, references, corpus, config["related_problem"]["source"],
                                             checkpoint_dir, state["run_id"], records)
            else:
                records_list = [records[q["id"]] for q in selected]
            if index_fingerprints(config) != state["indexes"]:
                raise ValueError("Persisted indexes changed during evaluation; results were not published.")
            current_config = yaml.safe_load((ROOT / "config.yml").read_text())
            if input_fingerprints(current_config, selected) != fingerprints:
                raise ValueError("Benchmark or production code changed during evaluation; results were not published.")
            run["index_fingerprints"] = state["indexes"]
            metrics = write_reports(results_dir, run, records_list)
            state["status"] = "completed"
            atomic_json(checkpoint_dir / "run.json", state)
            print(f"Saved {results_dir / 'summary.md'}; failed executions: {metrics['failed_executions']}", flush=True)
        finally:
            for worker in workers:
                client = getattr(worker["pipeline"].llm, "client", None)
                if client:
                    client.close()


if __name__ == "__main__":
    main()
