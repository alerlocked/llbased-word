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

# ---------------------------------------------------------------------------
# Noise patterns — OCR artifacts that should not be treated as data
# ---------------------------------------------------------------------------
_NOISE_PATTERNS: List[re.Pattern] = [
    # Signature names (编制/校对/审核/标检/批准 + person names)
    re.compile(r"^(编制|校对|审核|标检|批准|会签)[：:]?\s*$"),
    # Date stamps
    re.compile(r"^\d{8}$"),  # 20240828
    re.compile(r"^\d{4}[年\-/.]\d{1,2}[月\-/.]?\d{0,2}[日]?$"),
    # Page / change markers
    re.compile(r"^(页数|页码|更改单号|共\d+页|第\d+页)[：:]?\s*$"),
    re.compile(r"^共\s*\d+\s*页"),  # "共X页" variants
    # Continuation markers — with and without parentheses
    re.compile(r".*[\(（]续[\)）]\s*$"),
    re.compile(r".*(?:明细表|过程卡|工艺卡片|文件目录|工艺规程)(?:续|序)\s*$"),
    # Section / table titles appearing as data values
    re.compile(
        r"^(?:工艺过程卡|配套明细表|装配工艺卡片|工艺文件目录|引用文件目录"
        r"|专用工艺装备明细表|主要材料消耗|辅助材料消耗|专用工具|封面)\s*$"
    ),
    # Product codes in wrong context (standalone, not in part_code field)
    re.compile(r"^(小产品|KA0-\d+-KZD)$"),
    # Signature lines
    re.compile(r"^[编制校对审核标检批准：:]+[_\s]*$"),
    # Standalone "M.2" or similar version markers
    re.compile(r"^M\.\d+$"),
    # Table header keywords appearing as data
    re.compile(r"^(?:工序号|工序名称|设备|工艺装备|准结|单件|总计|车间|产品工号)\s*$"),
]

# Keywords that indicate a row is metadata, not data
_METADATA_KEYWORDS = [
    "签名", "编制", "校对", "审核", "标检", "批准", "会签",
    "更改单号", "日期", "页数", "页码",
]

# Top Chinese surname first characters for person name detection
_COMMON_SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐"
    "费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄"
    "和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁"
    "牛石段侯武刘龙叶白田卓"
)

# Column keys that should NEVER contain person names
_CODE_LIKE_KEYS = {
    "part_code", "equipment_code", "component_code", "ref_code",
    "doc_number", "for_component_code",
}

# Column keys where values should be numeric
_NUMERIC_KEYS = {"seq", "step_no", "quantity", "per_set_qty", "batch_qty"}


def _is_person_name(value: str) -> bool:
    """Heuristic: is this value likely a Chinese person name?

    Checks: first char is a common surname + total length 2-4 chars,
    remaining chars are common CJK name characters.
    """
    if not value or len(value) < 2 or len(value) > 4:
        return False
    if value[0] not in _COMMON_SURNAMES:
        return False
    # Remaining chars should be CJK (not punctuation/ASCII)
    return all("一" <= c <= "鿿" for c in value[1:])


def validate_field_value(col_key: str, value: str) -> Optional[str]:
    """Check if a value is valid for the given column.

    Returns:
        None if valid, or a warning string describing the issue.
    """
    if not value or not value.strip():
        return None

    stripped = value.strip()

    # Person name in code/designation field
    if col_key in _CODE_LIKE_KEYS and _is_person_name(stripped):
        return f"person name '{stripped}' in code field '{col_key}'"

    # Non-numeric value in numeric field
    if col_key in _NUMERIC_KEYS:
        # Allow empty or pure digits / decimals
        clean = stripped.replace(".", "").replace("-", "")
        if clean and not clean.isdigit():
            return f"non-numeric '{stripped}' in numeric field '{col_key}'"

    # Page number pattern in name/description field
    if "name" in col_key or col_key == "step_desc":
        if re.match(r"^(?:共?\d+页|第?\d+页|页数|页码)", stripped):
            return f"page marker '{stripped}' in name field '{col_key}'"

    return None


def validate_filled_rows(
    rows: List[Dict[str, Any]],
    column_keys: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Validate and clean filled rows by checking field-level constraints.

    Replaces invalid values with empty string instead of removing rows.
    """
    if not rows:
        return rows

    keys = column_keys or list(rows[0].keys())
    for row in rows:
        for key in keys:
            val = row.get(key)
            if val and isinstance(val, str):
                warning = validate_field_value(key, val)
                if warning:
                    logger.debug("field_validation_cleaned", warning=warning)
                    row[key] = ""

    return rows


def _is_noise_row(row: List[str]) -> bool:
    """Check if a table row is OCR noise (signature, date, header continuation, etc.)."""
    joined = " ".join(cell.strip() for cell in row if cell.strip())
    if not joined:
        return True

    # Check individual cells against noise patterns
    for cell in row:
        stripped = cell.strip()
        if not stripped:
            continue
        for pat in _NOISE_PATTERNS:
            if pat.match(stripped):
                return True

    # Check if the row is mostly metadata keywords
    keyword_hits = sum(1 for kw in _METADATA_KEYWORDS if kw in joined)
    if keyword_hits >= 2:
        return True

    # Check for signature-line pattern: "编制:___审核:___校对:___"
    if "编制" in joined and ("审核" in joined or "校对" in joined):
        return True

    return False

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

    # Extract data rows (after header), filtering noise
    results: Dict[str, List[str]] = {col.key: [] for col in structured_cols}
    data_start = best_header_idx + 1

    for row in rows[data_start:]:
        # Skip noise rows (signatures, dates, page headers, etc.)
        if _is_noise_row(row):
            continue
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
    key_map: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Merge structured field values with LLM-generated unstructured values.

    Args:
        structured_values: {col_key: [val1, val2, ...]} from extraction.
        unstructured_slots: [{"row": N, "slot": "key", "value": "..."}] from LLM.
        row_count: Total rows to generate.
        key_map: Optional label→key mapping for normalizing LLM slot names.

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
                slot_name = slot.get("slot", "")
                # Safety net: normalize label→key if key_map provided
                if key_map and slot_name in key_map:
                    slot_name = key_map[slot_name]
                row[slot_name] = slot.get("value", "")

        rows.append(row)

    # Filter out rows where all values are empty/None or are noise
    rows = _filter_empty_rows(rows)
    rows = _filter_noise_rows(rows)
    # Field-level validation: clean invalid values (person names in code fields, etc.)
    all_keys = list(structured_values.keys())
    rows = validate_filled_rows(rows, all_keys)
    return rows


def _filter_empty_rows(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Remove rows where every value is empty string or None.

    Returns:
        Rows with at least one non-empty value.
    """
    filtered = []
    for row in rows:
        has_value = any(v not in ("", None) for v in row.values())
        if has_value:
            filtered.append(row)
    return filtered


def _filter_noise_rows(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Remove rows that are OCR metadata noise (signatures, dates, headers).

    Applied after merging structured + unstructured data as a safety net.
    """
    filtered = []
    for row in rows:
        # Check all string values in the row
        all_values = [str(v) for v in row.values() if v not in ("", None)]

        is_noise = False
        for val in all_values:
            for pat in _NOISE_PATTERNS:
                if pat.match(val.strip()):
                    is_noise = True
                    break
            if is_noise:
                break

        # Also check for signature-line patterns spanning multiple fields
        joined = " ".join(all_values)
        if "编制" in joined and ("审核" in joined or "校对" in joined):
            is_noise = True

        if not is_noise:
            filtered.append(row)

    return filtered


# ---------------------------------------------------------------------------
# Flow-step parsing — extract process flow steps from G19a output
# ---------------------------------------------------------------------------

def parse_flow_steps(flow_output: Any) -> Dict[str, Any]:
    """Parse G19a flow_chart output into a structured step list.

    Accepts:
      - A list of step-name strings: ["装前准备", "对接", ...]
      - A list of dicts: [{"step_no": 1, "step_name": "装前准备"}, ...]
      - A string of comma/newline-separated step names

    Returns:
        {
            "step_count": int,
            "steps": [{"step_no": N, "step_name": "..."}, ...]
        }
    """
    steps: List[Dict[str, Any]] = []

    if isinstance(flow_output, list):
        for i, item in enumerate(flow_output):
            if isinstance(item, str):
                steps.append({"step_no": i + 1, "step_name": item.strip()})
            elif isinstance(item, dict):
                name = item.get("step_name") or item.get("name") or item.get("title", "")
                no = item.get("step_no") or item.get("seq") or (i + 1)
                steps.append({"step_no": int(no), "step_name": str(name).strip()})
    elif isinstance(flow_output, str):
        # Split by comma or newline
        parts = re.split(r"[,\n]", flow_output)
        for i, part in enumerate(parts):
            clean = part.strip().lstrip("0123456789.)、 \t")
            if clean:
                steps.append({"step_no": i + 1, "step_name": clean})

    return {
        "step_count": len(steps),
        "steps": steps,
    }
