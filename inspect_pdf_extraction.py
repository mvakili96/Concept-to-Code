"""Compare native pypdf and structured extraction on a small, explicit page selection."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import yaml
import pypdf

from pdf_ingestion import PDFExtractor, file_sha256
from pdf_tables import chunk_table_document


ROOT = Path(__file__).resolve().parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=ROOT / "docs/pdf-extraction-pilot.yml")
    parser.add_argument("--limit", type=int, help="Inspect only the first N selected pages")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    plan = yaml.safe_load(args.plan.read_text())
    config = yaml.safe_load((ROOT / "config.yml").read_text())
    # This inspection chooses Docling without changing config.yml or the production indexes.
    documents_config = {**config["documents"], "extraction": {
        **config["documents"].get("extraction", {}), "parser": "docling", "source_overrides": {}}}
    extractor = PDFExtractor(documents_config)
    paths = {path.name: path for path in ROOT.glob(config["documents"]["pdf_glob"])}
    selected = []
    for sample in plan["samples"]:
        for page in sample["pages"]:
            selected.append((sample, page))
    if args.limit:
        selected = selected[:args.limit]
    # Validate the complete selection before downloading models or starting conversion.
    if len({(sample["source"], page) for sample, page in selected}) != len(selected):
        raise ValueError("The extraction pilot contains duplicate source/page pairs.")
    page_counts = {}
    for sample, page in selected:
        if sample["source"] not in paths:
            raise FileNotFoundError(f"Missing pilot PDF: {sample['source']}")
        if sample["source"] not in page_counts:
            page_counts[sample["source"]] = len(pypdf.PdfReader(paths[sample["source"]]).pages)
        if type(page) is not int or not 1 <= page <= page_counts[sample["source"]]:
            raise ValueError("Pilot pages must be one-based physical PDF page numbers.")
    output = ROOT / plan["output_dir"]
    output.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    report = {"schema_version": "1.0.0", "created_at": datetime.now(timezone.utc).isoformat(),
              "extraction_settings": extractor.settings, "llm_calls": 0,
              "review_status": "automated_extraction_only", "pages": []}
    markdown = ["# PDF extraction pilot", "",
                "Structured native prose and optional table rows. Figure interpretation and OCR are disabled.", "",
                "Compare each page image against both text views. Region coordinates are PDF points from the top-left.", ""]
    # Rendering is local and optional only outside the pilot dependency installation.
    import pypdfium2 as pdfium
    for index, (sample, page) in enumerate(selected, start=1):
        source = sample["source"]
        print(f"[{index}/{len(selected)}] {source}, physical page {page}", flush=True)
        tick = perf_counter()
        extracted = extractor.extract(paths[source], pages=[page])
        data = extracted["structured_pages"][page]
        table_chunks = [chunk for doc in extracted["documents"] if doc.metadata.get("content_type") == "table"
                        for chunk in chunk_table_document(doc, config["chunking"]["chunk_size"])]
        prefix = f"{index:02d}-page-{page}"
        # Render the original PDF. This is the visual reference, not an LLM-generated image.
        with pdfium.PdfDocument(paths[source]) as pdf:
            pdf_page = pdf[page - 1]
            bitmap = pdf_page.render(scale=1.25)
            bitmap.to_pil().save(output / f"{prefix}.png")
            bitmap.close()
            pdf_page.close()
        (output / f"{prefix}-pypdf.txt").write_text(extracted["raw_pages"][page], encoding="utf-8")
        (output / f"{prefix}-docling.txt").write_text(data["text"], encoding="utf-8")
        (output / f"{prefix}-tables.txt").write_text("\n\n".join(
            f"CHUNK: {chunk.metadata['chunk_id']}\n{chunk.page_content}" for chunk in table_chunks), encoding="utf-8")
        item = {"source": source, "source_sha256": file_sha256(paths[source]), "page": page,
                "focus": sample["focus"], "seconds": round(perf_counter() - tick, 3),
                "raw_characters": len(extracted["raw_pages"][page]),
                "structured_characters": len(data["text"]),
                "element_counts": dict(Counter(element["content_type"] for element in data["elements"])),
                "offset_basis": "docling_page_text", **data,
                "table_chunks": [{"text": chunk.page_content, **chunk.metadata} for chunk in table_chunks]}
        report["pages"].append(item)
        markdown.extend([f"## {source}, physical page {page}", "", sample["focus"], "",
                         f"![Original PDF page]({prefix}.png)", "",
                         f"[Raw pypdf text]({prefix}-pypdf.txt) · [Structured prose]({prefix}-docling.txt)", "",
                         f"[Table chunks with repeated headers and linked notes]({prefix}-tables.txt)", "",
                         f"Detected elements: `{json.dumps(item['element_counts'])}`", "",
                         "| Type | Element ID | Bounding box | Indexed text span |",
                         "|---|---|---|---|"])
        for element in data["elements"]:
            span = f"{element['start']}:{element['end']}" if element["start"] is not None else "Excluded"
            markdown.append(f"| {element['content_type']} | {element['element_id']} | {element['bbox']} | {span} |")
        markdown.extend(["", *data["warnings"], ""])
        for chunk in table_chunks:
            markdown.extend([f"### Table rows {chunk.metadata['row_start']}–{chunk.metadata['row_end']}", "",
                             "```text", chunk.page_content, "```", ""])
            if chunk.metadata["oversized_table_row"]:
                markdown.extend(["This complete row and its headers/notes exceed chunk_size. Nothing was truncated.", ""])
    report["elapsed_seconds"] = round(perf_counter() - started, 3)
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "review.md").write_text("\n".join(markdown), encoding="utf-8")
    print(f"Pilot saved to {output / 'review.md'}. Production indexes were not modified.", flush=True)


if __name__ == "__main__":
    main()
