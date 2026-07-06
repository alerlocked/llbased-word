"""
Knowledge Extractor — Extract structured data from parsed QJ903 process documents.

Reads content.html from material directories, identifies QJ903 table types,
and extracts structured data into material_catalog, process_steps tables.

Uses dynamic header detection (table_schemas.py) to map column positions
at runtime, so parsing is not coupled to any specific document layout.

Supported table roles:
  tooling_list  — 专用工艺装备明细表
  tool_gauge    — 专用工/量具明细表 (split-column: tools + gauges)
  material_main — 主要材料消耗工艺定额
  material_aux  — 辅助材料消耗工艺定额
  material_bom  — 配套明细表
  process_flow  — 工艺流程图 (horizontal layout)
  process_card  — 工艺过程卡
  assembly_card — 装配工艺卡片
"""
import re
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from bs4 import BeautifulSoup, Tag

from app.shared.logging import get_logger
from app.services.table_schemas import (
    ROLE_SCHEMAS,
    detect_header_row,
    detect_header_row_with_optional,
    detect_split_column,
    expand_with_subheader,
    extract_row_data,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Table-type identification
# ---------------------------------------------------------------------------

# QJ903 standard markers
TABLE_ROLES = {
    "G10a": "tooling_list",
    "B12a": "tool_gauge",
    "G12a": "material_main",
    "G14a": "material_aux",
    "G18a": "material_bom",
    "G18b": "material_bom",
    "G19a": "process_flow",
    "G22a": "process_card",
    "G22b": "process_card",
    "G25a": "assembly_card",
    "G25b": "assembly_card",
    "G1a":  "cover",
    "G4a":  "assembly_card",
    "G5a":  "process_card",
}

# Chinese title patterns — order matters, more specific first
TITLE_PATTERNS = [
    ("tooling_list",  ["专用工艺装备明细", "工装明细表"]),
    ("tool_gauge",    ["专用工", "量具明细表", "工具、量具", "工、量具明细"]),
    ("material_main", ["主要材料消耗", "主要材料"]),
    ("material_aux",  ["辅助材料消耗", "辅助材料"]),
    ("material_bom",  ["配套明细表", "配套明细"]),
    ("process_flow",  ["工艺流程图"]),
    ("process_card",  ["工艺过程卡"]),
    ("assembly_card", ["装配工艺卡片", "装配工艺卡"]),
    ("file_ref",      ["引(借)用文件目录", "借用文件"]),
    ("file_dir",      ["工艺文件目录"]),
    ("cover",         ["封面"]),
]


def _classify_table(table: Tag) -> Optional[str]:
    """Identify table type from QJ903 markers or Chinese title patterns.

    Uses the FIRST ROW of the table for title matching, which avoids
    false positives from file names in directory tables.
    """
    text = table.get_text(separator=" ", strip=True)

    # QJ903 markers first
    for marker, role in TABLE_ROLES.items():
        if marker in text:
            return role

    # Chinese title patterns — match against FIRST ROW only
    first_row = table.find("tr")
    if first_row:
        first_row_text = first_row.get_text(separator=" ", strip=True)
        for role, patterns in TITLE_PATTERNS:
            for p in patterns:
                if p in first_row_text:
                    return role

    # Fallback: check first ~150 chars (second row sometimes has the title)
    header_text = text[:150]
    for role, patterns in TITLE_PATTERNS:
        for p in patterns:
            if p in header_text:
                return role

    return None


def _rows(table: Tag) -> List[List[str]]:
    """Extract all cells from a <table> as list-of-lists."""
    result: List[List[str]] = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(separator=" ", strip=True) for td in tr.find_all(["td", "th"])]
        if any(c.strip() for c in cells):
            result.append(cells)
    return result


def _build_grid(table: Tag) -> List[List[str]]:
    """Build a proper 2D grid resolving colspan/rowspan.

    Returns a list of rows where every row has the same number of columns,
    and column indices are consistent across all rows. Cells with colspan>1
    or rowspan>1 are replicated into all spanned positions.

    Empty rows (all cells empty) are filtered out.
    """
    html_rows: List[List[Tag]] = []
    for tr in table.find_all("tr"):
        html_rows.append(list(tr.find_all(["td", "th"])))

    if not html_rows:
        return []

    # First pass: determine grid width
    max_cols = 0
    for cells in html_rows:
        col_count = sum(int(c.get("colspan", 1)) for c in cells)
        max_cols = max(max_cols, col_count)

    num_rows = len(html_rows)

    # Initialize grid with empty strings
    grid: List[List[Optional[str]]] = [[None] * max_cols for _ in range(num_rows)]

    # Fill grid
    for r, cells in enumerate(html_rows):
        c = 0
        for cell in cells:
            # Advance past cells already filled by rowspan from above
            while c < max_cols and grid[r][c] is not None:
                c += 1
            if c >= max_cols:
                break

            text = cell.get_text(separator=" ", strip=True)
            colspan = int(cell.get("colspan", 1))
            rowspan = int(cell.get("rowspan", 1))

            for dr in range(rowspan):
                for dc in range(colspan):
                    if r + dr < num_rows and c + dc < max_cols:
                        grid[r + dr][c + dc] = text

            c += colspan

    # Convert to list-of-str-lists, filtering fully empty rows
    result: List[List[str]] = []
    for row in grid:
        str_row = [c if c is not None else "" for c in row]
        if any(c.strip() for c in str_row):
            result.append(str_row)
    return result


# ---------------------------------------------------------------------------
# Metadata / noise filtering
# ---------------------------------------------------------------------------

# Values that should never appear as extracted data
_SKIP_VALUES: Set[str] = {
    "校对", "标检", "批准", "编写", "审核", "签名", "签字",
    "共2页", "共3页", "共4页", "共5页", "共1页",
    "阶段标记", "阶段", "合计", "总计", "会签",
    "更改标记", "更改单号", "录入", "标检", "阶段",
}

# Substrings that indicate a header / metadata row
_HEADER_SUBSTRINGS = {
    "产品工号", "产品数字", "零、部、组", "工艺文件编号",
    "工艺文件名称", "编制单位", "签名", "日期",
    "会签", "标签", "栏", "更改标记",
}


def _is_valid_name(text: str) -> bool:
    """Check if text is a valid data name (not metadata/noise)."""
    t = text.strip()
    if not t or len(t) < 2:
        return False
    if re.match(r"^\d{1,3}$", t):
        return False
    if re.match(r"^\d{8}$", t):
        return False
    if t in _SKIP_VALUES:
        return False
    return True


def _is_metadata_row(row: List[str]) -> bool:
    """Check if an entire row is metadata (signatures, headers, dates)."""
    joined = " ".join(row)
    # Signature rows always have dates like 20240828
    if re.search(r"\b20\d{6}\b", joined):
        return True
    for sub in _HEADER_SUBSTRINGS:
        if sub in joined:
            return True
    return False


def _is_grid_metadata_row(row: List[str]) -> bool:
    """Check if a grid row (with expanded rowspan/colspan) is metadata.

    Unlike _is_metadata_row, this tolerates rowspan-expanded cells like
    '会签' which appear in every row. Only checks for signature dates
    and metadata patterns outside the rowspan zone.
    """
    # Signature rows always have dates like 20240828
    joined = " ".join(row)
    if re.search(r"\b20\d{6}\b", joined):
        return True
    # Check for metadata keywords beyond the first 2 columns
    # (first 2 cols are typically rowspan-expanded '会签')
    tail = " ".join(row[2:]) if len(row) > 2 else ""
    for sub in ("阶段标记", "编制单位", "更改标记", "更改单号"):
        if sub in tail:
            return True
    return False


def _strip_leading_empty(row: List[str]) -> List[str]:
    """Remove leading empty/sequence-number cells."""
    data = [c.strip() for c in row]
    while data and (not data[0] or re.match(r"^\d{1,3}$", data[0])):
        data.pop(0)
    return data


# ---------------------------------------------------------------------------
# Main extractor
# ---------------------------------------------------------------------------

class KnowledgeExtractor:
    """Extract materials, tools, and process steps from parsed documents."""

    def __init__(self, documents_dir: Path | str | None = None):
        if documents_dir is None:
            from app.config import settings
            self._docs_dir = settings.DOCUMENTS_DIR
        else:
            self._docs_dir = Path(documents_dir)

    # -- public entry point --------------------------------------------------

    def extract_from_doc(self, doc_id: str) -> Dict[str, Any]:
        """Parse one document and return structured extraction results."""
        doc_dir = self._docs_dir / doc_id
        html_path = self._resolve_html(doc_dir)
        if html_path is None:
            logger.warning(f"[知识提取] 文档目录无 HTML: {doc_dir}")
            return self._empty_result(doc_id)

        html_content = html_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html_content, "html.parser")

        materials: List[Dict] = []
        tools: List[Dict] = []
        process_steps: List[Dict] = []

        # Two-pass strategy:
        # Pass 1: classify each table and build expanded grid
        classified: List[tuple] = []  # (role, grid_rows)
        for table in soup.find_all("table"):
            role = _classify_table(table)
            grid_rows = _build_grid(table)
            if role and grid_rows:
                classified.append((role, grid_rows))

        # Pass 2: extract by role with role-specific parsers
        for role, rows in classified:
            if role == "tooling_list":
                tools.extend(self._parse_tooling_list(rows, doc_id))

            elif role == "tool_gauge":
                tools.extend(self._parse_tool_gauge_list(rows, doc_id))

            elif role in ("material_main", "material_aux"):
                materials.extend(self._parse_material_quota(rows, doc_id, role))

            elif role == "material_bom":
                materials.extend(self._parse_assembly_bom(rows, doc_id))

            elif role == "process_flow":
                process_steps.extend(self._parse_process_flow(rows, doc_id))

            elif role == "process_card":
                process_steps.extend(self._parse_process_card(rows, doc_id))

        # Deduplicate process steps by name
        seen_steps: Set[str] = set()
        unique_steps = []
        for s in process_steps:
            if s["step_name"] not in seen_steps:
                seen_steps.add(s["step_name"])
                unique_steps.append(s)
        process_steps = unique_steps

        logger.info(
            f"[知识提取] 文档 {doc_id}: "
            f"{len(materials)} 物料, {len(tools)} 工具, {len(process_steps)} 工序"
        )
        # 产关联（节点5）：工序 description 提物料/工具名匹配 catalog
        relations: Dict[str, List[str]] = {}
        _catalog_names = [m.get("name", "") for m in materials + tools if m.get("name")]
        for step in process_steps:
            _desc = step.get("description") or ""
            if not _desc:
                continue
            _matched = [n for n in _catalog_names if n and len(n) >= 2 and n in _desc]
            if _matched:
                relations[step["step_name"]] = _matched

        return {
            "doc_id": doc_id,
            "materials": materials,
            "tools": tools,
            "process_steps": process_steps,
            "relations": relations,
        }

    # -- persistence ---------------------------------------------------------

    def extract_and_save(self, doc_id: str, db_session) -> Dict[str, int]:
        """Extract from a document and persist into the database."""
        from app.models.database import MaterialCatalog, ProcessStep, Material

        data = self.extract_from_doc(doc_id)

        # 维度传递（revive-extract-funnel 节点2）：从 Material 行读 specialty，
        # 落到 MaterialCatalog/ProcessStep，让结构化查询支持型号/专业穿透。
        mat_specialty = None
        if doc_id.isdigit():
            _m = db_session.query(Material).filter(Material.id == int(doc_id)).first()
            if _m:
                mat_specialty = _m.specialty

        # Deduplicate & insert materials + tools (both go to material_catalog)
        existing = {
            (m.name, m.model) for m in
            db_session.query(MaterialCatalog.name, MaterialCatalog.model).all()
        }
        for item in data["materials"] + data["tools"]:
            key = (item["name"], item.get("model"))
            if key in existing:
                continue
            if mat_specialty and "specialty" not in item:
                item["specialty"] = mat_specialty
            row = MaterialCatalog(**{k: v for k, v in item.items() if v is not None})
            db_session.add(row)
            db_session.flush()
            existing.add(key)

        # Insert process steps
        for idx, item in enumerate(data["process_steps"]):
            if db_session.query(ProcessStep).filter_by(
                doc_id=item["doc_id"], step_name=item["step_name"]
            ).first():
                continue
            item["step_order"] = idx + 1
            if mat_specialty and "specialty" not in item:
                item["specialty"] = mat_specialty
            row = ProcessStep(**{k: v for k, v in item.items() if v is not None})
            db_session.add(row)
            db_session.flush()

        # 落关联（节点5）：StepMaterial（工序 description 提名匹配 → 物料/工具）
        from app.models.database import StepMaterial
        _rels = data.get("relations", {})
        for _step_name, _names in _rels.items():
            _step = db_session.query(ProcessStep).filter_by(
                doc_id=doc_id, step_name=_step_name
            ).first()
            if not _step:
                continue
            for _cname in _names:
                _cat = db_session.query(MaterialCatalog).filter_by(
                    source_doc=doc_id, name=_cname
                ).first()
                if not _cat:
                    continue
                if not db_session.query(StepMaterial).filter_by(
                    step_id=_step.id, catalog_id=_cat.id
                ).first():
                    db_session.add(StepMaterial(
                        step_id=_step.id, catalog_id=_cat.id, usage_type="referenced"
                    ))

        db_session.commit()
        mat_count = len(data["materials"]) + len(data["tools"])
        step_count = len(data["process_steps"])
        logger.info(f"[知识提取] 持久化完成: {mat_count} 物料+工具, {step_count} 工序")
        return {"materials": mat_count, "process_steps": step_count}

    # -- role-specific parsers -----------------------------------------------

    def _parse_tooling_list(self, rows: List[List[str]], doc_id: str) -> List[Dict]:
        """Parse 专用工艺装备明细表 using dynamic header detection."""
        results = []
        schema = ROLE_SCHEMAS["tooling_list"]
        header_idx, field_map = detect_header_row_with_optional(
            rows, schema.required, schema.optional,
        )
        if header_idx is None:
            return []
        # Expand with sub-header row (column names may be on next row)
        field_map = expand_with_subheader(rows, header_idx, field_map)

        for row in rows[header_idx + 1:]:
            clean = [c.strip() for c in row]
            if _is_grid_metadata_row(clean):
                continue
            if sum(1 for c in clean if c) < 2:
                continue
            data = extract_row_data(clean, field_map)
            if not data:
                continue
            code = data.get("code", "")
            name = data.get("name", "")
            if not _is_valid_name(name) and not _is_valid_name(code):
                continue
            results.append({
                "category": "tool",
                "name": name if _is_valid_name(name) else code,
                "model": code if _is_valid_name(name) else None,
                "spec": data.get("category"),
                "source_doc": doc_id,
            })
        return results

    def _parse_tool_gauge_list(self, rows: List[List[str]], doc_id: str) -> List[Dict]:
        """Parse 专用工、量具明细表 with split-column detection.

        Left half = tools, right half = gauges.
        """
        results = []

        # Try split-column detection first
        left_fields = ["name", "model"]
        right_fields = ["name", "model"]
        split_result = detect_split_column(rows, left_fields, right_fields)
        header_idx, left_map, right_map = split_result

        if header_idx is not None and left_map:
            # Expand with sub-header row
            left_map = expand_with_subheader(rows, header_idx, left_map)
            right_map = expand_with_subheader(rows, header_idx, right_map)

            for row in rows[header_idx + 1:]:
                clean = [c.strip() for c in row]
                if _is_grid_metadata_row(clean):
                    continue
                if sum(1 for c in clean if c) < 2:
                    continue

                # Left half: tools
                data = extract_row_data(clean, left_map)
                if data and _is_valid_name(data.get("name", "")):
                    results.append({
                        "category": "tool",
                        "name": data["name"],
                        "model": data.get("model"),
                        "source_doc": doc_id,
                    })

                # Right half: gauges
                if right_map:
                    data = extract_row_data(clean, right_map)
                    if data and _is_valid_name(data.get("name", "")):
                        results.append({
                            "category": "tool",
                            "name": data["name"],
                            "model": data.get("model"),
                            "source_doc": doc_id,
                        })
            return results

        # Fallback: simple header detection (no split)
        header_idx, field_map = detect_header_row_with_optional(
            rows, ["name"], ["model"],
        )
        if header_idx is None:
            return []
        field_map = expand_with_subheader(rows, header_idx, field_map)

        for row in rows[header_idx + 1:]:
            clean = [c.strip() for c in row]
            if _is_grid_metadata_row(clean):
                continue
            if sum(1 for c in clean if c) < 2:
                continue
            data = extract_row_data(clean, field_map)
            if data and _is_valid_name(data.get("name", "")):
                results.append({
                    "category": "tool",
                    "name": data["name"],
                    "model": data.get("model"),
                    "source_doc": doc_id,
                })
        return results

    def _parse_material_quota(self, rows: List[List[str]], doc_id: str, role: str) -> List[Dict]:
        """Parse 材料消耗工艺定额明细表 using dynamic header detection."""
        results = []
        cat = "consumable" if role == "material_main" else "auxiliary"

        header_idx, field_map = detect_header_row_with_optional(
            rows, ["material"], ["code", "name", "unit"],
        )
        if header_idx is None:
            return []
        field_map = expand_with_subheader(rows, header_idx, field_map)

        # Collect header texts to detect rowspan-expanded values
        header_row = rows[header_idx]
        header_texts = {col_i: text.strip() for col_i, text in enumerate(header_row) if text.strip()}

        for row in rows[header_idx + 1:]:
            clean = [c.strip() for c in row]
            if _is_grid_metadata_row(clean):
                continue
            if sum(1 for c in clean if c) < 2:
                continue
            data = extract_row_data(clean, field_map)
            if not data:
                continue

            material_name = data.get("material", "")

            # Skip if material name is the same as header text (rowspan expansion)
            mat_col = field_map.get("material", -1)
            if mat_col >= 0 and material_name == header_texts.get(mat_col, ""):
                continue

            if not _is_valid_name(material_name):
                continue

            # Unit from field_map or scan remaining cells
            unit = data.get("unit")
            if unit:
                # Skip if unit is header text (rowspan expansion)
                unit_col = field_map.get("unit", -1)
                if unit_col >= 0 and unit == header_texts.get(unit_col, ""):
                    unit = None
            if not unit:
                for c in clean:
                    if c in ("个", "件", "套", "kg", "m", "只", "根", "片", "米", "克", "副", "g"):
                        unit = c
                        break

            results.append({
                "category": cat,
                "name": material_name,
                "model": None,
                "standard_code": None,
                "spec": None,
                "unit": unit,
                "source_doc": doc_id,
            })
        return results

    def _parse_assembly_bom(self, rows: List[List[str]], doc_id: str) -> List[Dict]:
        """Parse 配套明细表 using dynamic header detection."""
        results = []
        header_idx, field_map = detect_header_row_with_optional(
            rows, ["code", "name"], ["quantity", "source"],
        )
        if header_idx is None:
            return []
        field_map = expand_with_subheader(rows, header_idx, field_map)

        for row in rows[header_idx + 1:]:
            clean = [c.strip() for c in row]
            if _is_grid_metadata_row(clean):
                continue
            if sum(1 for c in clean if c) < 2:
                continue
            data = extract_row_data(clean, field_map)
            if not data:
                continue

            code = data.get("code", "")
            name = data.get("name", "")
            source = data.get("source")

            if not _is_valid_name(code) and not _is_valid_name(name):
                continue

            part_name = name if _is_valid_name(name) else code
            part_code = code if code != part_name else None

            # Classify: if code starts with GB/QJ/GJB etc., it's a standard part
            category = "standard_part"
            if part_code and re.match(r"^[A-Z]{1,3}/[A-Z]", part_code):
                category = "standard_part"
            elif part_code and re.match(r"^[A-Z]{2,5}\d", part_code):
                category = "standard_part"
            else:
                category = "consumable"

            results.append({
                "category": category,
                "name": part_name,
                "model": part_code if part_code != part_name else None,
                "standard_code": part_code if part_code and re.match(r"^[A-Z]", part_code) else None,
                "spec": source,
                "source_doc": doc_id,
            })
        return results

    def _parse_process_flow(self, rows: List[List[str]], doc_id: str) -> List[Dict]:
        """Parse 工艺流程图 — horizontal layout with step names in cells.

        Scans rows after the header until hitting metadata rows (signatures,
        dates). Step names are Chinese strings with 3+ chars.
        """
        results = []
        seen: Set[str] = set()

        # Find where data starts — skip header rows with 产品工号 etc.
        data_start = 0
        for idx, row in enumerate(rows):
            joined = " ".join(row)
            if any(kw in joined for kw in ("产品工号", "工艺文件编号")):
                data_start = idx + 1
            # Also skip the row that has the QJ903 title
            if "工艺流程图" in joined:
                data_start = idx + 1

        for row in rows[data_start:]:
            # Stop at metadata rows (signatures, dates)
            if _is_grid_metadata_row(row):
                break

            for cell in row:
                cell = cell.strip()
                if not cell or len(cell) < 3:
                    continue
                if cell in _SKIP_VALUES or cell in ("会签",):
                    continue
                if re.match(r"^\d+$", cell):
                    continue
                if re.match(r"^[A-Z0-9\-\.]+$", cell):
                    continue
                if any(kw in cell for kw in ("签名", "日期", "编制", "审核",
                                               "产品", "工艺文件", "会签",
                                               "更改", "批准", "校对", "标检",
                                               "阶段", "页")):
                    continue
                if re.search(r"[\u4e00-\u9fff]{2,}", cell) and cell not in seen:
                    seen.add(cell)
                    results.append({
                        "doc_id": doc_id,
                        "step_name": cell,
                        "description": None,
                    })

        return results

    def _parse_process_card(self, rows: List[List[str]], doc_id: str) -> List[Dict]:
        """Parse 工艺过程卡 using dynamic header detection.

        Falls back to work-type anchor detection (钳/焊/车/铣) when header
        detection fails due to colspan-heavy layouts.
        """
        results = []
        seen: Set[str] = set()

        # Try dynamic header detection first
        header_idx, field_map = detect_header_row_with_optional(
            rows, ["step_name"],
            ["workshop", "description", "equipment", "step_no",
             "content", "aux_materials", "instruments"],
        )

        if header_idx is not None and "step_name" in field_map:
            field_map = expand_with_subheader(rows, header_idx, field_map)

            for row in rows[header_idx + 1:]:
                clean = [c.strip() for c in row]
                if _is_grid_metadata_row(clean):
                    continue
                if sum(1 for c in clean if c) < 2:
                    continue
                data = extract_row_data(clean, field_map)
                if not data:
                    continue

                step_name = data.get("step_name", "")
                if not _is_valid_name(step_name) or step_name in seen:
                    continue
                seen.add(step_name)

                desc_parts = []
                if data.get("description"):
                    desc_parts.append(data["description"])
                # G25a 工序内容/辅助材料/工装（节点5：关联落库需 content 提物料名）
                if data.get("content"):
                    desc_parts.append(data["content"])
                if data.get("aux_materials"):
                    desc_parts.append(f"辅料: {data['aux_materials']}")
                if data.get("instruments"):
                    desc_parts.append(f"工装: {data['instruments']}")
                if data.get("equipment"):
                    desc_parts.append(f"设备: {data['equipment']}")
                if data.get("workshop"):
                    desc_parts.append(f"车间: {data['workshop']}")

                results.append({
                    "doc_id": doc_id,
                    "step_name": step_name,
                    "description": "; ".join(desc_parts) or None,
                })
            return results

        # Fallback: work-type anchor detection (钳/焊/车/铣 etc.)
        for row in rows:
            if _is_grid_metadata_row(row):
                continue
            clean = [c.strip() for c in row]
            if sum(1 for c in clean if c) < 3:
                continue

            step_name = None
            workshop = None
            description = None
            equipment = None

            for i, cell in enumerate(clean):
                if cell in ("钳", "焊", "车", "铣", "磨", "镗", "铸", "锻", "装", "检",
                            "钳工", "焊工", "装配", "检验"):
                    for j in range(i - 1, -1, -1):
                        if clean[j] and re.match(r"^\d{1,3}$", clean[j]):
                            pass  # step_no, not used in output
                        elif clean[j] and workshop is None:
                            workshop = clean[j]
                    if i + 1 < len(clean) and _is_valid_name(clean[i + 1]):
                        step_name = clean[i + 1]
                    if i + 2 < len(clean) and _is_valid_name(clean[i + 2]):
                        description = clean[i + 2]
                    if i + 3 < len(clean) and _is_valid_name(clean[i + 3]):
                        equipment = clean[i + 3]
                    break

            if not step_name or not _is_valid_name(step_name):
                continue
            if step_name in seen:
                continue
            seen.add(step_name)

            desc_parts = []
            if description:
                desc_parts.append(description)
            if equipment:
                desc_parts.append(f"设备: {equipment}")
            if workshop:
                desc_parts.append(f"车间: {workshop}")

            results.append({
                "doc_id": doc_id,
                "step_name": step_name,
                "description": "; ".join(desc_parts) or None,
            })

        return results

    # -- helpers -------------------------------------------------------------

    def _empty_result(self, doc_id: str) -> Dict[str, Any]:
        return {"doc_id": doc_id, "materials": [], "tools": [], "process_steps": [], "relations": {}}

    def _resolve_html(self, doc_dir: Path) -> Optional[Path]:
        for name in ("content.html", "document.html"):
            p = doc_dir / name
            if p.exists():
                return p
        return None
