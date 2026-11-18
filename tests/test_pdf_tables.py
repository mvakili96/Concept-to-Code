"""Verify row/column meaning and provenance without Docling weights or LLM calls."""
import copy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import yaml

from main import RAGPipeline
from pdf_ingestion import extraction_settings, structured_pages
from pdf_tables import extract_table, table_document, chunk_table_document


def bbox(left=10, top=10, right=200, bottom=100):
    box = SimpleNamespace(l=left, t=top, r=right, b=bottom)
    box.to_top_left_origin = lambda height: box
    return box


def cell(text, row, column, header=False, row_span=1, col_span=1):
    return SimpleNamespace(text=text, start_row_offset_idx=row, end_row_offset_idx=row + row_span,
        start_col_offset_idx=column, end_col_offset_idx=column + col_span, row_span=row_span, col_span=col_span,
        column_header=header, row_header=False, row_section=False, bbox=bbox())


def source_table(values=None):
    values = values or [["Method", "Latency (ms)"], ["Sync", "50"], ["Async", "10"]]
    cells = [cell(text, row, column, header=row == 0)
             for row, values_row in enumerate(values) for column, text in enumerate(values_row)]
    table = SimpleNamespace(label="table", prov=[SimpleNamespace(page_no=7, bbox=bbox())],
        data=SimpleNamespace(num_rows=len(values), num_cols=len(values[0]), table_cells=cells),
        captions=[], footnotes=[])
    doc = SimpleNamespace(pages={7: SimpleNamespace(size=SimpleNamespace(height=800))},
                          iterate_items=lambda: iter([(table, 0)]))
    element = dict(element_id="book.pdf::page=7::element=stable", bbox=[10, 10, 200, 100],
                   bbox_origin="TOPLEFT", content_type="table", start=None, end=None)
    return table, doc, element


class TableExtractionTests(unittest.TestCase):
    def test_headers_values_units_and_linked_notes_have_original_anchors(self):
        item, doc, element = source_table()
        caption = SimpleNamespace(text="Table 2. Results at one client.", prov=item.prov)
        note = SimpleNamespace(text="Measured without network latency.", prov=item.prov)
        item.captions = [SimpleNamespace(resolve=lambda document: caption)]
        item.footnotes = [SimpleNamespace(resolve=lambda document: note)]
        table = extract_table(item, doc, element)
        self.assertEqual(table["header_rows"], [0])
        self.assertEqual(table["cells"][3]["text"], "50")
        self.assertEqual(table["cells"][3]["row_start"], 1)
        self.assertEqual(table["cells"][3]["column_start"], 1)
        self.assertEqual([value["text"] for value in table["notes"]], [caption.text, note.text])
        result = table_document(table, "book.pdf", "hash")
        self.assertIn('HEADER ROW 1: ["Method", "Latency (ms)"]', result.page_content)
        self.assertIn('ROW 2: ["Sync", "50"]', result.page_content)
        self.assertIn(caption.text, result.page_content)
        self.assertIn(note.text, result.page_content)
        self.assertEqual(result.metadata["page"], 7)

    def test_merged_headers_and_cells_preserve_their_column_spans(self):
        item, doc, element = source_table()
        item.data.num_rows = 4
        item.data.num_cols = 2
        item.data.table_cells = [cell("Timing", 0, 0, header=True, col_span=2),
            cell("Method", 1, 0, header=True), cell("Latency (ms)", 1, 1, header=True),
            cell("Shared method", 2, 0, row_span=2), cell("50", 2, 1), cell("10", 3, 1)]
        table = extract_table(item, doc, element)
        chunks = chunk_table_document(table_document(table, "book.pdf", "hash"), 1)
        self.assertEqual(len(chunks), 2)
        self.assertIn('HEADER ROW 1: ["Timing", "Timing"]', chunks[0].page_content)
        self.assertIn('HEADER ROW 2: ["Method", "Latency (ms)"]', chunks[1].page_content)
        self.assertIn('ROW 3: ["Shared method", "50"]', chunks[0].page_content)
        self.assertIn('ROW 4: ["Shared method", "10"]', chunks[1].page_content)
        self.assertEqual(chunks[0].metadata["table_cells"][3]["row_end"], 4)

    def test_invalid_spans_holes_overlaps_and_multi_page_tables_are_rejected(self):
        for issue in ("span", "hole", "overlap", "multi_page", "nonleading_header"):
            with self.subTest(issue=issue):
                item, doc, element = source_table()
                if issue == "span": item.data.table_cells[0].end_col_offset_idx = 3
                elif issue == "hole": item.data.table_cells.pop()
                elif issue == "overlap": item.data.table_cells.append(item.data.table_cells[-1])
                elif issue == "multi_page": item.prov.append(SimpleNamespace(page_no=8, bbox=bbox()))
                else: item.data.table_cells[-1].column_header = True
                with self.assertRaises(ValueError):
                    extract_table(item, doc, element)

    def test_notes_without_a_page_anchor_are_not_attached_by_guessing(self):
        item, doc, element = source_table()
        item.footnotes = [SimpleNamespace(resolve=lambda document: SimpleNamespace(text="Unanchored condition", prov=[]))]
        with self.assertRaisesRegex(ValueError, "note"):
            extract_table(item, doc, element)

    def test_table_without_header_labels_keeps_first_row_as_data(self):
        item, doc, element = source_table()
        for value in item.data.table_cells:
            value.column_header = False
        table = extract_table(item, doc, element)
        text = table_document(table, "book.pdf", "hash").page_content
        self.assertIn('ROW 1: ["Method", "Latency (ms)"]', text)
        self.assertNotIn("HEADER", text)

    def test_invalid_table_is_flagged_and_excluded_from_structured_pages(self):
        item, doc, _element = source_table()
        item.data.table_cells.pop()
        page = structured_pages(doc, "book.pdf", "hash", {7}, tables_enabled=True)[7]
        self.assertEqual(page["tables"], [])
        self.assertEqual(page["elements"][0]["table_status"], "excluded_invalid_structure")
        self.assertTrue(any("Missing cells" in note for note in page["warnings"]))


class TableChunkTests(unittest.TestCase):
    def table_document(self):
        item, doc, element = source_table([["Method", "Latency (ms)"], *[[f"Mode {i}", f"{i} ms"] for i in range(12)]])
        note = SimpleNamespace(text="Conditions: one client, warmed cache.", prov=item.prov)
        item.footnotes = [SimpleNamespace(resolve=lambda document: note)]
        return table_document(extract_table(item, doc, element), "book.pdf", "hash")

    def test_large_table_splits_only_between_rows_and_repeats_headers_and_notes(self):
        doc = self.table_document()
        chunks = chunk_table_document(doc, 170)
        self.assertGreater(len(chunks), 1)
        seen_rows = []
        for chunk in chunks:
            self.assertIn('HEADER ROW 1: ["Method", "Latency (ms)"]', chunk.page_content)
            self.assertIn("Conditions: one client, warmed cache.", chunk.page_content)
            self.assertLessEqual(len(chunk.page_content), 170)
            self.assertNotIn("table", chunk.metadata)
            self.assertEqual(chunk.metadata["offset_basis"], "docling_table_chunk_text")
            seen_rows.extend(range(chunk.metadata["row_start"], chunk.metadata["row_end"] + 1))
        self.assertEqual(seen_rows, list(range(2, 14)))
        self.assertEqual(len({chunk.metadata["chunk_id"] for chunk in chunks}), len(chunks))

    def test_small_table_stays_whole_and_oversized_rows_are_never_truncated(self):
        doc = self.table_document()
        self.assertEqual(len(chunk_table_document(doc, 10000)), 1)
        chunks = chunk_table_document(doc, 1)
        self.assertEqual(len(chunks), 12)
        self.assertTrue(all(chunk.metadata["oversized_table_row"] for chunk in chunks))
        self.assertIn('ROW 13: ["Mode 11", "11 ms"]', chunks[-1].page_content)

    def test_pipeline_indexes_tables_and_keeps_metadata_in_final_context(self):
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.config = yaml.safe_load((Path(__file__).parents[1] / "config.yml").read_text())
        pipeline.config["chunking"]["chunk_size"] = 170
        pipeline.config["chunking"]["chunk_overlap"] = 0
        chunks = pipeline.chunk_documents([self.table_document()])
        self.assertGreater(len(chunks), 1)
        _context, final = pipeline.build_context([(chunks[0], 1.0)])
        self.assertEqual(final[0]["content_type"], "table")
        self.assertEqual(final[0]["table_id"], chunks[0].metadata["table_id"])
        self.assertEqual(final[0]["table_notes"], chunks[0].metadata["table_notes"])
        self.assertIn("Latency (ms)", final[0]["text"])
        self.assertNotIn("parser=docling::start=", final[0]["chunk_id"])

    def test_table_toggle_changes_structured_index_settings(self):
        off = {"extraction": {"parser": "docling", "tables": {"enabled": False}}}
        on = copy.deepcopy(off)
        on["extraction"]["tables"]["enabled"] = True
        self.assertNotEqual(extraction_settings(off), extraction_settings(on))
        self.assertTrue(extraction_settings(on)["docling_options"]["do_table_structure"])
        on["extraction"]["tables"]["enabled"] = "false"
        with self.assertRaises(ValueError):
            extraction_settings(on)


if __name__ == "__main__":
    unittest.main()
