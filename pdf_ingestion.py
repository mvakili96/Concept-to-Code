"""Optional layout extraction. Raw pypdf text remains a separate source of provenance."""
import hashlib
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pypdf
from langchain_core.documents import Document
from pdf_tables import extract_table, table_document


EXTRACTION_SCHEMA_VERSION = 2
# Stage one indexes native prose only. Table reconstruction, OCR, and vision come later.
# Stage two optionally adds separate table Documents, preserving the original prose path.
TEXT_LABELS = {"text", "paragraph", "title", "section_header", "list_item", "code"}
DOCLING_OPTIONS = {
    "do_ocr": False,
    "do_table_structure": False,
    "do_picture_description": False,
    "do_picture_classification": False,
    "enable_remote_services": False,
}


def extraction_settings(documents_config):
    settings = documents_config.get("extraction", {})
    parser = settings.get("parser", "pypdf")
    overrides = settings.get("source_overrides", {})
    if parser not in {"pypdf", "docling"} or any(
        value not in {"pypdf", "docling"} for value in overrides.values()
    ):
        raise ValueError('PDF extraction parser must be "pypdf" or "docling".')
    # Redundant overrides do not change extraction or invalidate existing pypdf indexes.
    overrides = {source: value for source, value in overrides.items() if value != parser}
    result = {"schema_version": EXTRACTION_SCHEMA_VERSION, "parser": parser,
              "source_overrides": overrides}
    if "docling" in {parser, *overrides.values()}:
        result["docling_options"] = DOCLING_OPTIONS.copy()
        tables = settings.get("tables", {}).get("enabled", False)
        if type(tables) is not bool:
            raise ValueError("documents.extraction.tables.enabled must be true or false.")
        result["docling_options"]["do_table_structure"] = tables
    return result


def file_sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def package_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return None


class PDFExtractor:
    def __init__(self, documents_config):
        self.settings = extraction_settings(documents_config)
        self.converter = None

    def docling_converter(self):
        if self.converter is None:
            try:
                from docling.datamodel.base_models import InputFormat
                from docling.datamodel.pipeline_options import PdfPipelineOptions
                from docling.document_converter import DocumentConverter, PdfFormatOption
            except ImportError as error:
                raise RuntimeError(
                    "Docling extraction requires: pip install -r requirements-pdf.txt"
                ) from error
            options = PdfPipelineOptions(**self.settings["docling_options"])
            self.converter = DocumentConverter(format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=options)
            })
        return self.converter

    def extract(self, path, pages=None):
        path = Path(path)
        reader = pypdf.PdfReader(path)
        selected = list(range(1, len(reader.pages) + 1)) if pages is None else sorted(set(pages))
        if not selected or any(type(page) is not int or not 1 <= page <= len(reader.pages)
                               for page in selected):
            raise ValueError(f"Invalid one-based physical PDF pages for {path.name}.")
        parser = self.settings["source_overrides"].get(path.name, self.settings["parser"])
        raw_pages = {page: reader.pages[page - 1].extract_text() or "" for page in selected}
        result = {"documents": [], "raw_pages": raw_pages, "structured_pages": {},
                  "source": path.name, "parser": parser, "page_count": len(reader.pages)}
        if parser == "pypdf":
            result["documents"] = [Document(page_content=text, metadata={"source": path.name, "page": page})
                                   for page, text in raw_pages.items()]
            return result

        fingerprint = file_sha256(path)
        converter = self.docling_converter()
        # Page ranges are passed on the original PDF, so physical page numbers never reset to one.
        ranges = []
        for page in selected:
            if ranges and page == ranges[-1][1] + 1:
                ranges[-1][1] = page
            else:
                ranges.append([page, page])
        versions = {name: package_version(name) for name in
                    ("docling", "docling-core", "docling-parse", "docling-ibm-models", "pypdf")}
        for first, last in ranges:
            conversion = converter.convert(path, page_range=(first, last))
            status = getattr(conversion.status, "value", conversion.status)
            if status != "success":
                raise RuntimeError(f"Incomplete Docling conversion for {path.name}, pages {first}-{last}: {status}")
            converted = structured_pages(conversion.document, path.name, fingerprint,
                                         set(range(first, last + 1)),
                                         tables_enabled=self.settings["docling_options"]["do_table_structure"])
            result["structured_pages"].update(converted)
        if file_sha256(path) != fingerprint:
            raise RuntimeError(f"PDF changed during extraction: {path.name}")
        for page, data in result["structured_pages"].items():
            data["extractor_versions"] = versions
            result["documents"].append(Document(page_content=data["text"], metadata={
                "source": path.name, "page": page, "parser": "docling",
                "source_sha256": fingerprint, "offset_basis": "docling_page_text",
                "elements": data["elements"],
            }))
            result["documents"].extend(table_document(table, path.name, fingerprint) for table in data["tables"])
        return result


def structured_pages(document, source, fingerprint, selected, tables_enabled=False):
    """Adapt Docling reading-order elements without treating descriptions as source text."""
    pages = {page: {"text": "", "elements": [], "tables": [], "warnings": []} for page in sorted(selected)}
    for item, _level in document.iterate_items():
        label = getattr(item.label, "value", item.label)
        provenance = list(getattr(item, "prov", []))
        item_pages = {prov.page_no for prov in provenance}
        for prov in provenance:
            page = prov.page_no
            if page not in pages:
                continue
            bbox = prov.bbox.to_top_left_origin(document.pages[page].size.height)
            bounds = [float(bbox.l), float(bbox.t), float(bbox.r), float(bbox.b)]
            text = getattr(item, "text", "") or ""
            anchor = json.dumps([fingerprint, page, label, bounds, text], ensure_ascii=False)
            identifier = hashlib.sha256(anchor.encode("utf-8")).hexdigest()[:20]
            element = {"element_id": f"{source}::page={page}::element={identifier}",
                       "content_type": label, "bbox": bounds, "bbox_origin": "TOPLEFT",
                       "bbox_units": "PDF points", "start": None, "end": None,
                       "_text": text, "_single_page": len(item_pages) == 1}
            # Multi-page items need finer span mapping in a later stage, not guessed page assignments.
            if len(item_pages) > 1:
                pages[page]["warnings"].append(f"Multi-page element excluded from indexed text: {element['element_id']}")
            if label == "table" and tables_enabled:
                # Table extraction failures remain explicit. Flattened cell text stays excluded below.
                try:
                    table = extract_table(item, document, element)
                    # Internal prose-construction fields are not source metadata.
                    table["element"] = {key: value for key, value in element.items() if not key.startswith("_")}
                    pages[page]["tables"].append(table)
                    element["table_status"] = "extracted"
                except ValueError as error:
                    element["table_status"] = "excluded_invalid_structure"
                    pages[page]["warnings"].append(f"Table excluded: {element['element_id']}: {error}")
            pages[page]["elements"].append(element)
    for page, data in pages.items():
        visual_regions = [element["bbox"] for element in data["elements"]
                          if element["content_type"] in {"table", "picture"}]
        seen_text = set()
        for element in data["elements"]:
            text, single_page = element.pop("_text"), element.pop("_single_page")
            if element["content_type"] not in TEXT_LABELS or not text.strip() or not single_page:
                continue
            # With table reconstruction disabled, Docling may emit cell text as TextItems.
            # Detect it geometrically so flattened cells do not masquerade as ordinary prose.
            if any(region_contains_text(element["bbox"], region) for region in visual_regions):
                element["excluded_reason"] = "inside_detected_table_or_picture"
                continue
            if len(text) > 80 and text in seen_text:
                data["warnings"].append(f"Repeated native text detected. Inspect reading order: {element['element_id']}")
            seen_text.add(text)
            separator = "\n\n" if data["text"] else ""
            element["start"] = len(data["text"]) + len(separator)
            data["text"] += separator + text
            element["end"] = len(data["text"])
        if not data["text"].strip():
            data["warnings"].append("No indexable native prose. OCR is disabled in this stage.")
    return pages


def region_contains_text(text, region):
    left, top, right, bottom = text
    area = max(0, right - left) * max(0, bottom - top)
    overlap = max(0, min(right, region[2]) - max(left, region[0])) * max(0, min(bottom, region[3]) - max(top, region[1]))
    return area > 0 and overlap / area >= 0.8
