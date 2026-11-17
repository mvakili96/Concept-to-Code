"""Check provenance and build/load compatibility without model downloads or API calls."""
import copy
import json
import pickle
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import yaml
from langchain_core.documents import Document

from pdf_ingestion import PDFExtractor, extraction_settings, structured_pages
from main import RAGPipeline


ROOT = Path(__file__).resolve().parents[1]


def item(label, text="", page=7, bounds=(10, 20, 90, 50)):
    bbox = SimpleNamespace(l=bounds[0], t=bounds[1], r=bounds[2], b=bounds[3])
    bbox.to_top_left_origin = Mock(return_value=bbox)
    return SimpleNamespace(label=label, text=text, prov=[SimpleNamespace(page_no=page, bbox=bbox)])


def document(items, pages=(7,)):
    return SimpleNamespace(iterate_items=lambda: iter((value, 0) for value in items),
                           pages={page: SimpleNamespace(size=SimpleNamespace(height=800)) for page in pages})


class ExtractionTests(unittest.TestCase):
    def test_default_and_source_override_validation(self):
        settings = extraction_settings({})
        self.assertEqual(settings["parser"], "pypdf")
        self.assertNotIn("docling_options", settings)
        self.assertEqual(settings, extraction_settings({"extraction": {
            "source_overrides": {"book.pdf": "pypdf"}}}))
        with self.assertRaises(ValueError):
            extraction_settings({"extraction": {"parser": "unknown"}})

    def test_pypdf_preserves_original_strings_and_metadata(self):
        reader = SimpleNamespace(pages=[Mock(), Mock()])
        reader.pages[1].extract_text.return_value = "raw ﬁgure\n  original spacing"
        with patch("pdf_ingestion.pypdf.PdfReader", return_value=reader):
            extractor = PDFExtractor({"extraction": {"parser": "docling",
                                                     "source_overrides": {"book.pdf": "pypdf"}}})
            extractor.docling_converter = Mock(side_effect=AssertionError("Unexpected model load"))
            result = extractor.extract(Path("book.pdf"), [2])
        self.assertEqual(result["raw_pages"], {2: "raw ﬁgure\n  original spacing"})
        self.assertEqual(result["documents"][0].metadata, {"source": "book.pdf", "page": 2})
        self.assertEqual(result["documents"][0].page_content, reader.pages[1].extract_text.return_value)

    def test_invalid_page_selection_is_rejected(self):
        with patch("pdf_ingestion.pypdf.PdfReader", return_value=SimpleNamespace(pages=[Mock()])):
            for pages in ([], [0], [2], [True]):
                with self.subTest(pages=pages), self.assertRaises(ValueError):
                    PDFExtractor({}).extract(Path("book.pdf"), pages)

    def test_reading_order_and_regions_exclude_visual_and_marginal_content(self):
        values = [item("section_header", "A heading"), item("picture", bounds=(100, 20, 150, 50)), item("caption", "Caption"),
                  item("text", "Second paragraph."), item("table", "Cells are not native prose", bounds=(100, 60, 150, 90)),
                  item("page_footer", "Printed page 42")]
        pages = structured_pages(document(values), "book.pdf", "a" * 64, {7})
        page = pages[7]
        self.assertEqual(page["text"], "A heading\n\nSecond paragraph.")
        self.assertEqual(len(page["elements"]), 6)
        for element in page["elements"]:
            self.assertEqual(element["bbox_origin"], "TOPLEFT")
            if element["content_type"] in {"picture", "table", "caption", "page_footer"}:
                self.assertIsNone(element["start"])
        self.assertEqual(page["elements"][0]["bbox"], [10, 20, 90, 50])
        self.assertEqual(page["text"][page["elements"][3]["start"]:page["elements"][3]["end"]], "Second paragraph.")
        again = structured_pages(document(values), "book.pdf", "a" * 64, {7})
        self.assertEqual(page, again[7])

    def test_table_cell_text_is_not_indexed_as_unstructured_prose(self):
        values = [item("text", "Ordinary prose", bounds=(10, 10, 90, 30)),
                  item("table", bounds=(10, 100, 200, 200)),
                  item("text", "Misleading flattened table cells", bounds=(20, 120, 190, 150))]
        page = structured_pages(document(values), "book.pdf", "a" * 64, {7})[7]
        self.assertEqual(page["text"], "Ordinary prose")
        self.assertEqual(page["elements"][2]["excluded_reason"], "inside_detected_table_or_picture")
        self.assertIsNone(page["elements"][2]["start"])

    def test_multi_page_item_is_not_assigned_whole_to_each_page(self):
        value = item("text", "Ambiguous multi-page prose")
        value.prov.append(item("text", page=8).prov[0])
        pages = structured_pages(document([value], (7, 8)), "book.pdf", "a" * 64, {7, 8})
        self.assertTrue(all(not page["text"] and page["warnings"] for page in pages.values()))

    def test_docling_uses_original_page_range_and_keeps_raw_text(self):
        reader = SimpleNamespace(pages=[Mock() for _ in range(8)])
        for page in reader.pages:
            page.extract_text.return_value = "Raw text in another order"
        converted = document([item("text", "Structured prose")])
        converter = Mock()
        converter.convert.return_value = SimpleNamespace(status="success", document=converted)
        with patch("pdf_ingestion.pypdf.PdfReader", return_value=reader), \
             patch("pdf_ingestion.file_sha256", return_value="a" * 64):
            extractor = PDFExtractor({"extraction": {"parser": "docling"}})
            extractor.converter = converter
            result = extractor.extract(Path("book.pdf"), [7])
        converter.convert.assert_called_once_with(Path("book.pdf"), page_range=(7, 7))
        self.assertEqual(result["raw_pages"][7], "Raw text in another order")
        self.assertEqual(result["documents"][0].page_content, "Structured prose")
        self.assertEqual(result["documents"][0].metadata["page"], 7)
        self.assertEqual(result["documents"][0].metadata["offset_basis"], "docling_page_text")

    def test_partial_conversion_is_not_silently_indexed(self):
        reader = SimpleNamespace(pages=[Mock()])
        reader.pages[0].extract_text.return_value = "Raw text"
        with patch("pdf_ingestion.pypdf.PdfReader", return_value=reader), \
             patch("pdf_ingestion.file_sha256", return_value="a" * 64):
            extractor = PDFExtractor({"extraction": {"parser": "docling"}})
            extractor.converter = Mock()
            extractor.converter.convert.return_value = SimpleNamespace(status="partial_success")
            with self.assertRaisesRegex(RuntimeError, "Incomplete Docling"):
                extractor.extract(Path("book.pdf"), [1])


class PipelineIntegrationTests(unittest.TestCase):
    def pipeline(self):
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.config = copy.deepcopy(yaml.safe_load((ROOT / "config.yml").read_text()))
        return pipeline

    def test_chunk_offsets_and_element_regions_survive_context_assembly(self):
        pipeline = self.pipeline()
        data = structured_pages(document([item("text", "Grounded native prose.")]), "book.pdf", "a" * 64, {7})[7]
        doc = Document(page_content=data["text"], metadata={"source": "book.pdf", "page": 7,
            "parser": "docling", "offset_basis": "docling_page_text", "elements": data["elements"]})
        chunks = pipeline.chunk_documents([doc])
        self.assertEqual(len(chunks), 1)
        self.assertIn("parser=docling", chunks[0].metadata["chunk_id"])
        self.assertEqual(chunks[0].metadata["start_index"], 0)
        context, final_chunks = pipeline.build_context([(chunks[0], 1.0)])
        self.assertIn("Grounded native prose.", context)
        self.assertEqual(final_chunks[0]["elements"], data["elements"])
        self.assertEqual(final_chunks[0]["offset_basis"], "docling_page_text")
        raw = pipeline.chunk_documents([Document(page_content="Raw prose", metadata={"source": "book.pdf", "page": 7})])
        self.assertEqual(raw[0].metadata["chunk_id"], "book.pdf::page=7::start=0")

    def test_parser_switch_requires_rebuild_and_default_keeps_existing_settings(self):
        pipeline = self.pipeline()
        settings = pipeline.persisted_index_settings()
        existing = ROOT / "index-data/manifest.json"
        if existing.exists():
            self.assertEqual(settings, json.loads(existing.read_text())["index_settings"])
        self.assertNotIn("pdf_extraction", settings)
        pipeline.config["documents"]["extraction"]["parser"] = "docling"
        structured = pipeline.persisted_index_settings()
        self.assertNotEqual(structured, settings)
        self.assertFalse(structured["pdf_extraction"]["docling_options"]["do_ocr"])

    def test_persisted_structured_provenance_round_trip_and_legacy_loading(self):
        pipeline = self.pipeline()
        pipeline.available_sources = ["book.pdf"]
        pipeline.source_directory_names = {"book.pdf": "source_000"}
        pipeline.documents = [Document(page_content="Raw prose", metadata={"source": "book.pdf", "page": 1})]
        pipeline.chunks = pipeline.chunk_documents(pipeline.documents)
        pipeline.page_texts = {("book.pdf", 1): "raw exact PDF text"}
        pipeline.structured_pages = {("book.pdf", 1): {"text": "Structured text", "elements": []}}
        pipeline.global_bm25 = None
        pipeline.subset_bm25_cache = {}
        with tempfile.TemporaryDirectory() as temp:
            pipeline.persist_directory = Path(temp)
            for kind in ("flat", "hnsw"):
                directory = pipeline.dense_index_path(kind, "book.pdf")
                directory.mkdir(parents=True)
                for name in ("index.faiss", "index.pkl"):
                    (directory / name).touch()
            pipeline.save_index_data()
            other = self.pipeline()
            other.persist_directory = Path(temp)
            other.load_index_data()
            self.assertEqual(other.structured_pages, pipeline.structured_pages)
            self.assertEqual(other.page_texts, pipeline.page_texts)
            path = Path(temp) / "corpus.pkl"
            with path.open("rb") as stream:
                legacy = pickle.load(stream)
            legacy.pop("structured_pages")
            with path.open("wb") as stream:
                pickle.dump(legacy, stream)
            other.load_index_data()
            self.assertEqual(other.structured_pages, {})
            other.config["documents"]["extraction"]["parser"] = "docling"
            with self.assertRaisesRegex(ValueError, "rebuild"):
                other.load_index_data()


if __name__ == "__main__":
    unittest.main()
