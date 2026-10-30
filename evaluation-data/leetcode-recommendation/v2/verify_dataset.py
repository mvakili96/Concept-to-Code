"""Check benchmark data and rescan original PDFs; no inference or report updates."""
from collections import Counter
import hashlib
import json
import logging
from pathlib import Path
import re
import sys
import unicodedata

import yaml

ROOT = Path(__file__).resolve().parents[3]
DATA = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from evaluate_leetcode_recommendation import load_benchmark


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(text):
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    return " ".join(text.casefold().split())


def verify():
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    config = yaml.safe_load((ROOT / "config.yml").read_text())
    config["leetcode_recommendation_evaluation"].update(
        dataset_path=str(DATA / "leetcode_benchmark_v2.jsonl"),
        references_path=str(DATA / "references_v2.json"),
        manifest_path=str(DATA / "corpus_manifest_v2.json"))
    questions, references, manifest, corpus = load_benchmark(config)
    for name, expected in manifest["preparation_artifact_sha256"].items():
        if sha(DATA / name) != expected:
            raise ValueError(f"Preparation artifact hash mismatch: {name}")
    if len(questions) != 40 or len(references["topics"]) != 20:
        raise ValueError("Expected 40 questions and 20 topics.")
    if any(len([q for q in questions if q["topic_id"] == tid]) != 2 for tid in references["topics"]):
        raise ValueError("Each topic must have two wordings.")
    catalogue = [json.loads(line) for line in (DATA / "problem_catalogue_v2.jsonl").read_text().splitlines()]
    if [p["number"] for p in catalogue] != list(range(1, 4001)):
        raise ValueError("The source catalogue must contain all 4,000 unique identities.")
    original = {}
    for entry in catalogue:
        p = corpus.problem(entry["source"], entry["page"], entry["number"])
        if any(entry[k] != p[k] for k in ("title", "difficulty", "body_start", "body_end_exclusive")):
            raise ValueError(f"Problem identity mismatch: {entry['number']}")
        if hashlib.sha256(p["body"].encode()).hexdigest() != entry["body_sha256"]:
            raise ValueError(f"Problem body hash mismatch: {entry['number']}")
        original[p["number"]] = p
    ledger = [json.loads(line) for line in (DATA / "scan_ledger_v2.jsonl").read_text().splitlines()]
    for tid, topic in references["topics"].items():
        batches = sorted((b for b in ledger if b["topic_id"] == tid), key=lambda b: b["first_problem"])
        if [(b["first_problem"], b["last_problem"]) for b in batches] != [(i, i+99) for i in range(1,4001,100)]:
            raise ValueError(f"Missing or duplicated corpus coverage: {tid}")
        matched = []
        for batch in batches:
            ids = range(batch["first_problem"], batch["last_problem"] + 1)
            checksum = hashlib.sha256("\n".join(original[i]["body"] for i in ids).encode()).hexdigest()
            if checksum != batch["batch_body_sha256"] or batch["scanned_count"] != 100:
                raise ValueError(f"Batch checksum/count mismatch: {tid}")
            expected = [i for i in ids if all(re.search(pattern, normalize(original[i]["title"] + " " + original[i]["body"]))
                        for pattern in topic["screening_patterns"])]
            if expected != batch["matched_problem_numbers"]:
                raise ValueError(f"Full-statement scan mismatch: {tid}")
            reviewed = sorted(p["number"] for p in references["pairs"].values() if p["topic_id"] == tid and p["number"] in ids)
            if reviewed != batch["individually_source_audited_problem_numbers"]:
                raise ValueError(f"Audit ledger mismatch: {tid}")
            matched.extend(expected)
        if topic.get("control"):
            literal = normalize(topic["control"]["required_literal"])
            actual = [i for i, p in original.items() if literal in normalize(p["title"] + " " + p["body"])]
            if actual != matched:
                raise ValueError(f"Literal control scan mismatch: {tid}")
    positives = {"direct_match", "related_practice", "stretch_connection"}
    for tid, topic in references["topics"].items():
        expected = sorted(p["number"] for p in references["pairs"].values() if p["topic_id"] == tid and p["label"] in positives)
        if expected != topic["target_problem_numbers"]:
            raise ValueError(f"Recall targets omit an annotated positive: {tid}")
    print(f"Verified {len(questions)} questions, {len(references['pairs'])} source-anchored pair records, "
          f"and all 4,000 statements for each of {len(references['topics'])} topics.")
    print("Labels:", dict(Counter(p["label"] for p in references["pairs"].values())))
    print("Full text screening is verified; exhaustive semantic relevance is not claimed. No inference was run.")


if __name__ == "__main__":
    verify()
