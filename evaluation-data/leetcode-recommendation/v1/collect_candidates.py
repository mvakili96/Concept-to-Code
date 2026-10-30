"""Reproduce the v1.1 annotation pool offline; never call a model or production RAG."""
import argparse
from collections import Counter
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import random
import re
import unicodedata

from pypdf import PdfReader
from rank_bm25 import BM25Okapi
import yaml

ROOT = Path(__file__).resolve().parents[3]
DATA = Path(__file__).resolve().parent
STOP = set("a an the and or of to in on for by with from into each all is are be as at it that this given return you your".split())


def digest(path):
    with path.open("rb") as file:
        return hashlib.sha256(file.read()).hexdigest()


def normalize(text):
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"(?<=\w)[\-\u00ad\u2010\u2011][ \t]*\r?\n[ \t]*(?=\w)", "", text)
    return " ".join(text.casefold().split())


def tokens(text):
    return [word for word in re.findall(r"[a-z0-9]+", normalize(text)) if word not in STOP]


def grams(text):
    value = " ".join(tokens(text))
    return Counter(value[i:i + 4] for i in range(max(0, len(value) - 3)))


def collect():
    plan = json.loads((DATA / "collection_plan_v1_1.json").read_text())
    manifest_path = DATA / plan["base_manifest"]
    manifest = json.loads(manifest_path.read_text())
    for document in manifest["documents"]:
        if digest(ROOT / document["relative_path"]) != document["sha256"]:
            raise ValueError(f"Original PDF hash mismatch: {document['source']}")
    references_path = DATA / plan["base_references"]
    if digest(references_path) != manifest["data_sha256"][references_path.name]:
        raise ValueError("Base reference hash mismatch.")
    references = json.loads(references_path.read_text())
    isolation = yaml.safe_load((ROOT / "config.yml").read_text())["related_problem"]["problem_isolation"]
    document = next(d for d in manifest["documents"] if d["source"] == "LeetCode_4000_Problem_Reference.pdf")
    problems = []
    reader = PdfReader(ROOT / document["relative_path"])
    for page_number, page in enumerate(reader.pages, 1):
        raw = page.extract_text() or ""
        headers = list(re.finditer(isolation["header_pattern"], raw))
        if not headers:
            continue
        footers = list(re.finditer(isolation["footer_pattern"], raw))
        if len(footers) != 1:
            raise ValueError(f"Ambiguous footer on physical page {page_number}")
        for index, header in enumerate(headers):
            end = headers[index + 1].start() if index + 1 < len(headers) else footers[0].start()
            original = raw[header.end():end]
            start = header.end() + len(original) - len(original.lstrip())
            body = original.strip()
            problems.append(dict(source=document["source"], page=page_number, number=int(header["number"]),
                title=" ".join(header["title"].split()), difficulty=header["difficulty"],
                body_start=start, body_end_exclusive=start + len(body), body=body))
    problems.sort(key=lambda p: p["number"])
    if [p["number"] for p in problems] != list(range(1, 4001)):
        raise ValueError("Expected exactly the 4,000 unique source-owned problems.")
    # Constraints do not drive ranking; the exact full body remains available for audit.
    texts = [p["title"] + " " + re.split(r"(?i)\bconstraints\b", p["body"])[0] for p in problems]
    bm25 = BM25Okapi([tokens(text) for text in texts])
    document_grams = [grams(text) for text in texts]
    df = Counter()
    for counts in document_grams:
        df.update(counts.keys())
    idf = {gram: math.log((1 + len(problems)) / (1 + frequency)) + 1 for gram, frequency in df.items()}
    norms = [math.sqrt(sum((count * idf[gram]) ** 2 for gram, count in counts.items())) for counts in document_grams]
    rows = []
    rng = random.Random(plan["negative_sampling_seed"])
    for topic_id, query in plan["queries"].items():
        qgrams = grams(query)
        qweights = {gram: count * idf[gram] for gram, count in qgrams.items() if gram in idf}
        qnorm = math.sqrt(sum(weight ** 2 for weight in qweights.values()))
        similarity = [sum(weight * counts.get(gram, 0) * idf[gram] for gram, weight in qweights.items())
                      / (qnorm * norm) if qnorm and norm else 0 for counts, norm in zip(document_grams, norms)]
        selected = {}
        for method, scores in (("bm25_statement", bm25.get_scores(tokens(query))),
                               ("character_4gram_tfidf", similarity)):
            ranked = sorted(range(len(problems)), key=lambda i: (-float(scores[i]), problems[i]["number"]))
            for rank, index in enumerate(ranked[:plan["top_k_per_method"]], 1):
                selected.setdefault(index, []).append(dict(method=method, rank=rank, score=float(scores[index])))
        random_index = rng.choice([i for i in range(len(problems)) if i not in selected])
        selected[random_index] = [dict(method="seeded_random", rank=None, score=None)]
        for index in sorted(selected, key=lambda i: problems[i]["number"]):
            problem = problems[index]
            rows.append(dict(collection_id=plan["collection_id"], topic_id=topic_id,
                pair_id=f"{topic_id}::lc{problem['number']}", query=query,
                **{key: value for key, value in problem.items() if key != "body"},
                discovery=selected[index]))
    controls = []
    for topic_id, topic in references["topics"].items():
        if topic.get("control"):
            literal = normalize(topic["control"]["required_literal"])
            matches = [p["number"] for p in problems if literal in normalize(p["title"] + " " + p["body"])]
            controls.append(dict(topic_id=topic_id, required_literal=literal,
                                 scanned_problems=len(problems), matching_problem_numbers=matches))
    metadata = dict(collection_id=plan["collection_id"], scanned_problems=len(problems),
        candidate_pairs=len(rows), plan_sha256=digest(DATA / "collection_plan_v1_1.json"),
        source_sha256=document["sha256"], collector_sha256=digest(Path(__file__)),
        packages={name: version(name) for name in ("pypdf", "rank-bm25", "numpy", "PyYAML")},
        problem_isolation=isolation, controls=controls)
    return rows, metadata, problems


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="Write a new pool without overwriting curated files.")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pool_path, metadata_path = args.output_dir / "candidate_pool_v1_1.jsonl", args.output_dir / "collection_manifest_v1_1.json"
    if pool_path.exists() or metadata_path.exists():
        parser.error("Output already exists; choose a new directory.")
    rows, metadata, _ = collect()
    pool_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    metadata["candidate_pool_sha256"] = digest(pool_path)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scanned {metadata['scanned_problems']} statements; wrote {len(rows)} candidate pairs. No inference or labels generated.")
