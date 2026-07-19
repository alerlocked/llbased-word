"""
QJ903 table schema definitions and dynamic column mapping utilities.

Provides field alias registries, role schemas, and generic functions for
detecting table headers and extracting row data from QJ903-compliant
process documents.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import re

# ---------------------------------------------------------------------------
# A. Field alias registry — logical field → possible Chinese column names
# ---------------------------------------------------------------------------

FIELD_ALIASES: Dict[str, List[str]] = {
    "code":       ["代号", "编号", "零件代号"],
    "name":       ["名称"],
    "model":      ["型号或规格", "型号规格"],
    "category":   ["类别"],
    "quantity":   ["数量", "单套数量", "每装配件"],
    "unit":       ["计量单位"],
    "source":     ["来自何处", "交往何处"],
    "material":   ["材料名称、牌号", "名称、牌号", "材料"],
    "step_name":  ["工序名称"],
    "description": ["工序内容简述", "工序内容"],
    "equipment":  ["设备"],
    "workshop":   ["车间"],
    "step_no":    ["工序号", "序号"],
    "remark":     ["备注"],
}

# Build reverse lookup: Chinese alias → logical field name
_ALIAS_TO_FIELD: Dict[str, str] = {}
for _field, _aliases in FIELD_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_TO_FIELD[_alias] = _field


# ---------------------------------------------------------------------------
# B. Role schema definition
# ---------------------------------------------------------------------------

@dataclass
class RoleSchema:
    """Defines the expected fields and output category for a table role."""
    required: List[str]
    optional: List[str] = field(default_factory=list)
    output: str = "unknown"


ROLE_SCHEMAS: Dict[str, RoleSchema] = {
    "tooling_list":  RoleSchema(
        required=["code", "name"],
        optional=["category"],
        output="tool",
    ),
    "tool_gauge":    RoleSchema(
        required=["name"],
        optional=["model"],
        output="tool",
    ),
    "material_main": RoleSchema(
        required=["material"],
        optional=["code", "name", "unit"],
        output="consumable",
    ),
    "material_aux":  RoleSchema(
        required=["material"],
        optional=["code", "name", "unit"],
        output="auxiliary",
    ),
    "material_bom":  RoleSchema(
        required=["code", "name"],
        optional=["quantity", "source"],
        output="consumable",
    ),
    "process_card":  RoleSchema(
        required=["step_name"],
        optional=["workshop", "description", "equipment"],
        output="process",
    ),
    "assembly_card": RoleSchema(
        required=["step_name"],
        optional=["workshop", "description"],
        output="process",
    ),
}


# ---------------------------------------------------------------------------
# C. Generic detection & extraction functions
# ---------------------------------------------------------------------------

def detect_header_row(
    rows: List[List[str]],
    required_fields: List[str],
    max_scan: int = 10,
) -> Tuple[Optional[int], Dict[str, int]]:
    """Scan rows to find the header row and build field→column-index map.

    Returns (header_idx, field_map). If no suitable header found, returns
    (None, {}).

    Strategy: for each row, build two maps — one from exact matches (cell
    text exactly equals an alias) and one from substring matches (alias is
    a substring of cell text). Exact matches are strongly preferred.
    The row with the most exact matches wins; ties broken by total matches.
    """
    best_idx: Optional[int] = None
    best_exact = 0
    best_total = 0
    best_map: Dict[str, int] = {}

    for idx in range(min(len(rows), max_scan)):
        row = rows[idx]
        exact_map: Dict[str, int] = {}
        substr_map: Dict[str, int] = {}
        for col_i, cell in enumerate(row):
            cell_text = cell.strip()
            if cell_text in _ALIAS_TO_FIELD:
                fname = _ALIAS_TO_FIELD[cell_text]
                if fname not in exact_map:
                    exact_map[fname] = col_i
            else:
                for alias, fname in _ALIAS_TO_FIELD.items():
                    if alias in cell_text and fname not in substr_map and fname not in exact_map:
                        substr_map[fname] = col_i
                        break

        # Merge: exact matches take priority
        field_map = {**substr_map, **exact_map}
        exact_count = sum(1 for f in required_fields if f in exact_map)
        total_count = sum(1 for f in required_fields if f in field_map)

        if exact_count > best_exact or (exact_count == best_exact and total_count > best_total):
            best_exact = exact_count
            best_total = total_count
            best_idx = idx
            best_map = field_map

    if best_exact == 0 and best_total == 0:
        return None, {}

    return best_idx, best_map


def detect_header_row_with_optional(
    rows: List[List[str]],
    required_fields: List[str],
    optional_fields: List[str],
    max_scan: int = 10,
) -> Tuple[Optional[int], Dict[str, int]]:
    """Like detect_header_row but also includes optional field mappings.

    The header row is selected based on required field matches only.
    Optional fields are added to the map if found in the same row.
    """
    header_idx, field_map = detect_header_row(rows, required_fields, max_scan)
    if header_idx is None:
        return None, {}

    # Add optional fields from the same header row
    row = rows[header_idx]
    for col_i, cell in enumerate(row):
        cell_text = cell.strip()
        if cell_text in _ALIAS_TO_FIELD:
            fname = _ALIAS_TO_FIELD[cell_text]
            if fname in optional_fields and fname not in field_map:
                field_map[fname] = col_i
        else:
            for alias, fname in _ALIAS_TO_FIELD.items():
                if alias in cell_text and fname in optional_fields and fname not in field_map:
                    field_map[fname] = col_i
                    break

    return header_idx, field_map


def extract_row_data(
    row: List[str],
    field_map: Dict[str, int],
) -> Optional[Dict[str, str]]:
    """Extract data from a single row using the field→column mapping.

    Returns a dict of {field_name: cell_value} for fields with non-empty
    values, or None if all mapped values are empty.
    """
    result: Dict[str, str] = {}
    for fname, col_idx in field_map.items():
        if col_idx < len(row):
            val = row[col_idx].strip()
            if val:
                result[fname] = val
    return result if result else None


def detect_split_column(
    rows: List[List[str]],
    left_fields: List[str],
    right_fields: List[str],
    max_scan: int = 10,
) -> Tuple[Optional[int], Dict[str, int], Dict[str, int]]:
    """Detect a split-column layout (e.g., tools on left, gauges on right).

    Returns (header_idx, left_map, right_map). The split point is determined
    by finding a "序号" column that appears after the left section columns.
    """
    best_idx: Optional[int] = None
    best_left: Dict[str, int] = {}
    best_right: Dict[str, int] = {}
    best_score = 0

    for idx in range(min(len(rows), max_scan)):
        row = rows[idx]

        # Find all occurrences of "序号" — second one marks split point
        seq_indices = [
            col_i for col_i, cell in enumerate(row)
            if cell.strip() in ("序号",)
        ]

        if len(seq_indices) < 2:
            continue

        split_col = seq_indices[1]

        left_map: Dict[str, int] = {}
        right_map: Dict[str, int] = {}

        for col_i, cell in enumerate(row):
            cell_text = cell.strip()
            # Determine which alias it matches
            matched_field = None
            if cell_text in _ALIAS_TO_FIELD:
                matched_field = _ALIAS_TO_FIELD[cell_text]
            else:
                for alias, fname in _ALIAS_TO_FIELD.items():
                    if alias in cell_text:
                        matched_field = fname
                        break

            if matched_field is None:
                continue

            if col_i < split_col:
                if matched_field in left_fields and matched_field not in left_map:
                    left_map[matched_field] = col_i
            else:
                if matched_field in right_fields and matched_field not in right_map:
                    right_map[matched_field] = col_i

        score = len(left_map) + len(right_map)
        if score > best_score:
            best_score = score
            best_idx = idx
            best_left = left_map
            best_right = right_map

    if best_score == 0:
        return None, {}, {}

    return best_idx, best_left, best_right


# Expand field_map to next row for multi-row headers
def expand_with_subheader(
    rows: List[List[str]],
    header_idx: int,
    field_map: Dict[str, int],
) -> Dict[str, int]:
    """Expand field_map with columns from the row below the header.

    Useful when the actual column header (e.g., '代号', '名称') is on the
    row below the group header (e.g., '零件', '专用工艺装备').
    """
    if header_idx + 1 >= len(rows):
        return field_map

    expanded = dict(field_map)
    sub_row = rows[header_idx + 1]
    for col_i, cell in enumerate(sub_row):
        cell_text = cell.strip()
        if cell_text in _ALIAS_TO_FIELD:
            fname = _ALIAS_TO_FIELD[cell_text]
            if fname not in expanded:
                expanded[fname] = col_i
        else:
            for alias, fname in _ALIAS_TO_FIELD.items():
                if alias in cell_text and fname not in expanded:
                    expanded[fname] = col_i
                    break

    return expanded
