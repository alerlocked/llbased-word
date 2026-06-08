"""
Structured field extractor — extracts structured field values from source text.

Uses pattern matching (via FIELD_ALIASES from table_schemas) to extract
structured fields directly from source document text, bypassing LLM calls.
"""
import re
from typing import Any, Dict, List, Optional

from app.services.template_types import TemplateColumn
from app.services.table_schemas import FIELD_ALIASES
from app.shared.logging import get_logger

logger = get_logger(__name__)

# Map template column keys to FIELD_ALIASES logical field names
# for structured matching
_COLUMN_TO_ALIAS: Dict[str, str] = {
    "workshop": "workshop",
    "step_no": "step_no",
    "step_name": "step_name",
    "equipment": "equipment",
    "aux_materials": "material",
    "instruments": "equipment",
    "time_setup": "time_setup",
    "time_per_piece": "time_per_piece",
    "time_total": "time_total",
    "material_desc": "material",
    "unit": "unit",
    "quantity": "quantity",
    "equipment_code": "code",
    "equipment_name": "name",
    "tool_name": "name",
    "tool_spec": "model",
    "tool_quantity": "quantity",
    "gauge_name": "name",
    "gauge_spec": "model",
    "gauge_quantity": "quantity",
    "part_code": "code",
    "part_name": "name",
    "qty_per_assembly": "quantity",
    "source": "source",
    "ref_code": "code",
    "ref_name": "name",
    "doc_name": "name",
    "step_desc": "description",
}

# Regex patterns for extracting structured fields from text rows
_PATTERN_WORKSHOP = re.compile(r"车间\s*[:：]?\s*(\S+)")
_PATTERN_STEP_NO = re.compile(r"工序号\s*[:：]?\s*(\d+)")
_PATTERN_STEP_NAME = re.compile(r"工序名称\s*[:：]?\s*(\S+)")
_PATTERN_EQUIPMENT = re.compile(r"设备\s*[:：]?\s*(.+?)(?:\n|$)")
_PATTERN_TIME_SETUP = re.compile(r"准结\s*[:：]?\s*([\d.]+)")
_PATTERN_TIME_PIECE = re.compile(r"单件\s*[:：]?\s*([\d.]+)")
_PATTERN_TIME_TOTAL = re.compile(r"总计\s*[:：]?\s*([\d.]+)")


def extract_structured_fields(
    chapter_code: str,
    structured_cols: List[TemplateColumn],
    source_text: str,
) -> Dict[str, List[str]]:
    """Extract structured field values from source text by pattern matching.

    For each structured column, scans the source text for rows matching
    the column's label or known aliases and collects extracted values.

    Args:
        chapter_code: Chapter code (e.g. "G25a") for logging.
        structured_cols: Columns with fill_type="structured".
        source_text: Raw source document text for this chapter.

    Returns:
        {column_key: [value1, value2, ...]} — values per row.
        Empty list means extraction failed for that field.
    """
    if not source_text or not source_text.strip():
        return {col.key: [] for col in structured_cols}

    results: Dict[str, List[str]] = {}

    # Strategy depends on source text structure.
    # If the text contains table-like rows (| separated or aligned columns),
    # parse rows. Otherwise, use line-by-line extraction.

    rows = _parse_source_rows(source_text)

    if not rows:
        # Fallback: whole-text pattern matching for singleton fields
        results = _extract_singleton_fields(structured_cols, source_text)
    else:
        # Table-like: try to match columns from header + extract per-row
        results = _extract_tabular_fields(structured_cols, rows, source_text)

    logger.info(
        "structured_extraction_done",
        chapter_code=chapter_code,
        fields_found={k: len(v) for k, v in results.items()},
    )

    return results


def _parse_source_rows(text: str) -> List[List[str]]:
    """Parse source text into table rows.

    Detects Markdown tables (| separated) or tab-separated rows.
    Returns empty list if no table structure found.
    """
    lines = text.strip().split("\n")
    md_rows: List[List[str]] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            # Markdown table row
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            # Skip separator rows (|---|---|)
            if all(re.match(r"^[-:]+$", c) for c in cells):
                continue
            md_rows.append(cells)

    if md_rows:
        return md_rows

    # Try tab-separated rows
    tab_rows: List[List[str]] = []
    for line in lines:
        if "\t" in line:
            cells = [c.strip() for c in line.split("\t")]
            if len(cells) >= 2:
                tab_rows.append(cells)

    return tab_rows


def _extract_singleton_fields(
    structured_cols: List[TemplateColumn],
    text: str,
) -> Dict[str, List[str]]:
    """Extract fields that appear once (singleton) from full text."""
    results: Dict[str, List[str]] = {}

    for col in structured_cols:
        values: List[str] = []

        # Try matching by column label
        label = col.label
        pattern = re.compile(re.escape(label) + r"\s*[:：]?\s*(.+?)(?:\n|$)")
        match = pattern.search(text)
        if match:
            values.append(match.group(1).strip())

        # Try matching by FIELD_ALIASES
        alias_name = _COLUMN_TO_ALIAS.get(col.key)
        if not values and alias_name:
            aliases = FIELD_ALIASES.get(alias_name, [])
            for alias in aliases:
                pat = re.compile(re.escape(alias) + r"\s*[:：]?\s*(.+?)(?:\n|$)")
                m = pat.search(text)
                if m:
                    values.append(m.group(1).strip())
                    break

        results[col.key] = values

    return results


def _extract_tabular_fields(
    structured_cols: List[TemplateColumn],
    rows: List[List[str]],
    full_text: str,
) -> Dict[str, List[str]]:
    """Extract fields from table-like source text.

    Detects header row using FIELD_ALIASES, then extracts values per data row.
    """
    if not rows:
        return {col.key: [] for col in structured_cols}

    # Build column label -> col_key mapping for structured columns
    label_to_key: Dict[str, str] = {}
    for col in structured_cols:
        label_to_key[col.label] = col.key
        # Also register aliases
        alias_name = _COLUMN_TO_ALIAS.get(col.key)
        if alias_name:
            for alias in FIELD_ALIASES.get(alias_name, []):
                label_to_key[alias] = col.key

    # Find header row: the row with the most matches to our labels
    best_header_idx = -1
    best_count = 0
    best_col_map: Dict[str, int] = {}  # col_key -> column index

    for i, row in enumerate(rows[:5]):  # scan first 5 rows
        col_map: Dict[str, int] = {}
        for col_i, cell in enumerate(row):
            cell_text = cell.strip()
            for label, key in label_to_key.items():
                if label in cell_text and key not in col_map:
                    col_map[key] = col_i
                    break

        if len(col_map) > best_count:
            best_count = len(col_map)
            best_header_idx = i
            best_col_map = col_map

    if best_count == 0:
        # No header found, fall back to singleton extraction
        return _extract_singleton_fields(structured_cols, full_text)

    # Extract data rows (after header)
    results: Dict[str, List[str]] = {col.key: [] for col in structured_cols}
    data_start = best_header_idx + 1

    for row in rows[data_start:]:
        for col in structured_cols:
            col_idx = best_col_map.get(col.key)
            if col_idx is not None and col_idx < len(row):
                val = row[col_idx].strip()
                if val:
                    results[col.key].append(val)

    return results


def merge_structured_with_unstructured(
    structured_values: Dict[str, List[str]],
    unstructured_slots: List[Dict[str, Any]],
    row_count: int,
) -> List[Dict[str, Any]]:
    """Merge structured field values with LLM-generated unstructured values.

    Args:
        structured_values: {col_key: [val1, val2, ...]} from extraction.
        unstructured_slots: [{"row": N, "slot": "key", "value": "..."}] from LLM.
        row_count: Total rows to generate.

    Returns:
        List of row dicts with both structured and unstructured fields.
    """
    rows: List[Dict[str, Any]] = []

    for row_idx in range(row_count):
        row: Dict[str, Any] = {}

        # Fill structured fields
        for col_key, values in structured_values.items():
            if row_idx < len(values):
                row[col_key] = values[row_idx]
            else:
                row[col_key] = ""

        # Fill unstructured fields from LLM output
        for slot in unstructured_slots:
            if slot.get("row") == row_idx + 1:
                row[slot["slot"]] = slot.get("value", "")

        rows.append(row)

    return rows
