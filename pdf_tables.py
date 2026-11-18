"""Keep table rows, headers, and their source regions together during retrieval."""
import json

from langchain_core.documents import Document


def extract_table(item, document, element):
    if len(item.prov) != 1:
        raise ValueError("Multi-region or multi-page table requires explicit cell-to-page mapping.")
    data = item.data
    rows, columns = data.num_rows, data.num_cols
    if rows < 1 or columns < 1 or not data.table_cells:
        raise ValueError("Table has no reconstructed cells.")
    page = item.prov[0].page_no
    table_id = element["element_id"] + "::table"
    grid = [[None] * columns for _ in range(rows)]
    cells, headers = [], set()
    for index, cell in enumerate(data.table_cells):
        r0, r1 = cell.start_row_offset_idx, cell.end_row_offset_idx
        c0, c1 = cell.start_col_offset_idx, cell.end_col_offset_idx
        if (any(type(value) is not int for value in (r0, r1, c0, c1))
                or not 0 <= r0 < r1 <= rows or not 0 <= c0 < c1 <= columns
                or r1 - r0 != cell.row_span or c1 - c0 != cell.col_span):
            raise ValueError("Cell row/column spans are invalid.")
        for row in range(r0, r1):
            for column in range(c0, c1):
                if grid[row][column] is not None:
                    raise ValueError("Overlapping cells make the table structure ambiguous.")
                grid[row][column] = index
        if cell.column_header:
            headers.update(range(r0, r1))
        bounds = None
        if cell.bbox is not None:
            bbox = cell.bbox.to_top_left_origin(document.pages[page].size.height)
            bounds = [float(bbox.l), float(bbox.t), float(bbox.r), float(bbox.b)]
        cells.append({"cell_id": f"{table_id}::cell={index}", "text": cell.text,
                      "row_start": r0, "row_end": r1, "column_start": c0, "column_end": c1,
                      "column_header": cell.column_header, "row_header": cell.row_header,
                      "row_section": cell.row_section, "bbox": bounds})
    if any(index is None for row in grid for index in row):
        raise ValueError("Missing cells cannot safely be interpreted as empty values.")
    if sorted(headers) != list(range(len(headers))) or len(headers) == rows:
        raise ValueError("Column headers are not a leading block followed by data rows.")
    notes = []
    # Only Docling-linked captions/footnotes are attached. Proximity alone does not prove association.
    for kind in ("captions", "footnotes"):
        for reference in getattr(item, kind):
            note = reference.resolve(document)
            if not note.prov or {prov.page_no for prov in note.prov} != {page}:
                raise ValueError("A linked table note lacks an unambiguous same-page anchor.")
            boxes = []
            for prov in note.prov:
                bbox = prov.bbox.to_top_left_origin(document.pages[page].size.height)
                boxes.append([float(bbox.l), float(bbox.t), float(bbox.r), float(bbox.b)])
            notes.append({"kind": kind, "text": note.text, "page": page, "bboxes": boxes})
    return {"table_id": table_id, "page": page, "element": element.copy(),
            "num_rows": rows, "num_columns": columns, "header_rows": sorted(headers),
            "cells": cells, "grid": grid, "notes": notes}


def render_table(table, row_indices):
    lines = []
    for note in table["notes"]:
        lines.append(f"TABLE {'CAPTION' if note['kind'] == 'captions' else 'NOTE'}: {note['text']}")
    if any(cell["row_end"] - cell["row_start"] > 1 or cell["column_end"] - cell["column_start"] > 1
           for cell in table["cells"]):
        lines.append("FORMAT: Merged cell text repeats in each covered row/column position.")
    # Keep column positions explicit, including blank cells and headers containing units.
    for row in table["header_rows"] + list(row_indices):
        values = [table["cells"][index]["text"] for index in table["grid"][row]]
        kind = "HEADER ROW" if row in table["header_rows"] else "ROW"
        lines.append(f"{kind} {row + 1}: {json.dumps(values, ensure_ascii=False)}")
    return "\n".join(lines)


def table_document(table, source, fingerprint):
    body = range(len(table["header_rows"]), table["num_rows"])
    return Document(page_content=render_table(table, body), metadata={
        "source": source, "page": table["page"], "parser": "docling",
        "source_sha256": fingerprint, "content_type": "table", "table": table,
        "offset_basis": "docling_table_serialization", "table_id": table["table_id"],
        "elements": [table["element"]],
    })


def chunk_table_document(document, chunk_size):
    table = document.metadata["table"]
    groups, current = [], []
    for row in range(len(table["header_rows"]), table["num_rows"]):
        if current and len(render_table(table, current + [row])) > chunk_size:
            groups.append(current)
            current = []
        current.append(row)
    if current:
        groups.append(current)
    chunks = []
    for group in groups:
        text = render_table(table, group)
        selected_rows = set(table["header_rows"] + group)
        cell_indices = sorted({index for row in selected_rows for index in table["grid"][row]})
        metadata = {key: value for key, value in document.metadata.items() if key != "table"}
        metadata.update(chunk_id=f"{table['table_id']}::rows={group[0] + 1}-{group[-1] + 1}",
                        row_start=group[0] + 1, row_end=group[-1] + 1,
                        table_header_rows=[row + 1 for row in table["header_rows"]],
                        table_cells=[table["cells"][index] for index in cell_indices],
                        table_notes=table["notes"],
                        # Repeated headers mean this is not a contiguous original-page character span.
                        start_index=0, offset_basis="docling_table_chunk_text",
                        oversized_table_row=len(text) > chunk_size)
        chunks.append(Document(page_content=text, metadata=metadata))
    return chunks
