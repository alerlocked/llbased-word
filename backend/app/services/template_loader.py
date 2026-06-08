"""
Template loader — loads and validates template JSON files.

Provides utilities to extract fillable slots, build prompts for AI,
and separate editor-visible chapters from PDF-only fields.
"""
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.template_types import TemplateChapter, TemplateColumn
from app.shared.logging import get_logger

logger = get_logger(__name__)

# Cache loaded templates
_template_cache: Dict[str, Dict[str, Any]] = {}

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def load_template(template_id: str) -> Dict[str, Any]:
    """Load a template JSON file by template_id.

    Args:
        template_id: The template_id field from JSON (e.g. "assembly_process_cable")

    Returns:
        Parsed template dict.

    Raises:
        FileNotFoundError: If no matching template file found.
        ValueError: If template validation fails.
    """
    if template_id in _template_cache:
        return _template_cache[template_id]

    # Search for template file matching template_id
    template_file = _find_template_file(template_id)
    if not template_file:
        raise FileNotFoundError(f"Template not found: {template_id}")

    with open(template_file, "r", encoding="utf-8") as f:
        template = json.load(f)

    # Validate
    _validate_template(template)
    _template_cache[template_id] = template
    return template


def _find_template_file(template_id: str) -> Optional[Path]:
    """Find template JSON file by template_id."""
    if not TEMPLATES_DIR.exists():
        return None

    for f in TEMPLATES_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("template_id") == template_id:
                return f
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return None


def _validate_template(template: Dict[str, Any]) -> None:
    """Basic validation of template structure."""
    required_keys = ["template_id", "template_name", "chapters", "chapter_order"]
    for key in required_keys:
        if key not in template:
            raise ValueError(f"Template missing required key: {key}")

    chapter_codes = {ch["code"] for ch in template["chapters"]}
    for ordered_code in template["chapter_order"]:
        if ordered_code not in chapter_codes:
            raise ValueError(
                f"chapter_order contains '{ordered_code}' not found in chapters"
            )


def get_chapters(template: Dict[str, Any]) -> List[TemplateChapter]:
    """Parse all chapters from template into TemplateChapter objects."""
    return [TemplateChapter.from_dict(ch) for ch in template["chapters"]]


def get_chapter_by_code(
    template: Dict[str, Any], code: str
) -> Optional[TemplateChapter]:
    """Get a single chapter by its code."""
    for ch in template["chapters"]:
        if ch["code"] == code:
            return TemplateChapter.from_dict(ch)
    return None


def get_fillable_slots(chapter: TemplateChapter) -> List[TemplateColumn]:
    """Extract columns where ai_filled=True.

    Args:
        chapter: Parsed chapter object.

    Returns:
        List of columns that should be filled by AI.
    """
    return [col for col in chapter.columns if col.ai_filled]


def get_columns_by_fill_type(chapter: TemplateChapter) -> Dict[str, List[TemplateColumn]]:
    """Group chapter columns by fill_type.

    Args:
        chapter: Parsed chapter object.

    Returns:
        {"structured": [...cols], "unstructured": [...cols]}
    """
    structured: List[TemplateColumn] = []
    unstructured: List[TemplateColumn] = []
    for col in chapter.columns:
        if col.fill_type == "unstructured":
            unstructured.append(col)
        else:
            structured.append(col)
    return {"structured": structured, "unstructured": unstructured}
@dataclass
class GenerationPhase:
    """One phase of the generation pipeline."""
    phase: int
    description: str
    chapter_codes: List[str]
    output_key: Optional[str] = None
    depends_on: Optional[str] = None


def get_generation_phases(template: Dict[str, Any]) -> List[GenerationPhase]:
    """Parse generation_phases from template into ordered Phase objects.

    Returns a single default phase (all editor-visible chapters) when the
    template does not define explicit phases.
    """
    raw_phases = template.get("generation_phases")
    if not raw_phases:
        # Fallback: all editor-visible chapters in one phase
        editor_codes = [ch.code for ch in get_editor_chapters(template)]
        return [GenerationPhase(
            phase=1,
            description="default",
            chapter_codes=editor_codes,
        )]

    phases: List[GenerationPhase] = []
    for p in raw_phases:
        phases.append(GenerationPhase(
            phase=p["phase"],
            description=p.get("description", ""),
            chapter_codes=p["chapter_codes"],
            output_key=p.get("output_key"),
            depends_on=p.get("depends_on"),
        ))
    phases.sort(key=lambda x: x.phase)
    return phases


def get_editor_chapters(template: Dict[str, Any]) -> List[TemplateChapter]:
    """Return chapters visible in the editor (editor_visible != False)."""
    result = []
    for ch_data in template["chapters"]:
        if ch_data.get("editor_visible", True):
            result.append(TemplateChapter.from_dict(ch_data))
    return result


def get_footer_fields(template: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return footer fields (PDF-only, not shown in editor)."""
    footer = template.get("footer_fields", {})
    return footer.get("fields", []) if isinstance(footer, dict) else []


def build_fill_prompt(chapter: TemplateChapter) -> str:
    """Generate a JSON schema prompt for WritingAgent template filling.

    The prompt constrains AI to output only structured JSON values,
    no Markdown tables or free text.

    Args:
        chapter: The chapter to generate a fill prompt for.

    Returns:
        Prompt string describing expected JSON output format.
    """
    table_type = chapter.table_type

    # Types that don't use top-level columns — route first
    if table_type == "dual_list":
        return _build_dual_list_prompt(chapter)
    elif table_type == "flow_chart":
        return _build_flow_chart_prompt(chapter)

    # Types that use top-level columns — check slots
    slots = get_fillable_slots(chapter)
    if not slots:
        return ""

    if table_type == "single_row_list":
        return _build_single_row_prompt(chapter, slots)
    elif table_type == "process_card":
        return _build_process_card_prompt(chapter, slots)
    else:
        # fields type (e.g. cover page)
        return _build_fields_prompt(chapter)


def _build_single_row_prompt(
    chapter: TemplateChapter, slots: List[TemplateColumn]
) -> str:
    """Build prompt for single_row_list table type."""
    slot_desc = ", ".join(f'"{s.key}"({s.label})' for s in slots)
    all_cols = ", ".join(f'"{c.key}"({c.label})' for c in chapter.columns)

    return (
        f"章节「{chapter.title}」({chapter.code})，表格类型：行列表。\n"
        f"AI 需填充的列：{slot_desc}\n"
        f"完整列定义：{all_cols}\n"
        f"指导：{chapter.ai_guidance}\n\n"
        f"输出格式：JSON 数组，每个元素是一行数据，键为列 key。\n"
        f'示例：[{{"seq": 1, "{slots[0].key}": "...", ...}}, ...]\n'
        f"只输出 JSON，不要输出 Markdown 表格、不要解释。"
    )


def _build_process_card_prompt(
    chapter: TemplateChapter, slots: List[TemplateColumn]
) -> str:
    """Build prompt for process_card table type (G25a)."""
    slot_desc = ", ".join(f'"{s.key}"({s.label})' for s in slots)
    all_cols = ", ".join(f'"{c.key}"({c.label})' for c in chapter.columns)

    sub_sections_desc = ""
    if chapter.sub_sections:
        sub_parts = [f'"{s["key"]}"({s["label"]})' for s in chapter.sub_sections]
        sub_sections_desc = f"\n附加子段落：{', '.join(sub_parts)}"

    return (
        f"章节「{chapter.title}」({chapter.code})，表格类型：工序卡片。\n"
        f"AI 需填充的列：{slot_desc}\n"
        f"完整列定义：{all_cols}\n"
        f"指导：{chapter.ai_guidance}\n"
        f"{sub_sections_desc}\n\n"
        f"输出格式：JSON 数组，每个元素是一道工序的数据，键为列 key。\n"
        f'"content" 列是工序主体内容，包含子工步描述。\n'
        f"只输出 JSON，不要输出 Markdown 表格、不要解释。"
    )


def _build_dual_list_prompt(
    chapter: TemplateChapter,
) -> str:
    """Build prompt for dual_list table type (e.g. B12a)."""
    left = chapter.left_section or {}
    right = chapter.right_section or {}

    left_cols = left.get("columns", [])
    right_cols = right.get("columns", [])

    left_slots = [
        c for c in left_cols
        if c.get("ai_filled")
    ]
    right_slots = [
        c for c in right_cols
        if c.get("ai_filled")
    ]

    left_desc = ", ".join(f'"{c["key"]}"({c["label"]})' for c in left_slots)
    right_desc = ", ".join(f'"{c["key"]}"({c["label"]})' for c in right_slots)

    left_title = left.get("title", "")
    right_title = right.get("title", "")

    return (
        f"章节「{chapter.title}」({chapter.code})，表格类型：左右双列表。\n"
        f"左半「{left_title}」AI 填充列：{left_desc}\n"
        f"右半「{right_title}」AI 填充列：{right_desc}\n"
        f"指导：{chapter.ai_guidance}\n\n"
        f"输出格式：JSON 对象，包含 left 和 right 两个数组。\n"
        f'示例：{{"left": [{{"tool_seq": 1, ...}}], "right": [{{"gauge_seq": 1, ...}}]}}\n'
        f"只输出 JSON，不要输出 Markdown 表格、不要解释。"
    )


def _build_flow_chart_prompt(chapter: TemplateChapter) -> str:
    """Build prompt for flow_chart type (e.g. G19a)."""
    return (
        f"章节「{chapter.title}」({chapter.code})，表格类型：工艺流程。\n"
        f"指导：{chapter.ai_guidance}\n\n"
        f"输出格式：有序字符串数组，每个元素是一个工序步骤名称。\n"
        f'示例：["装前准备", "安装密封圈", "舱段对接", ...]\n'
        f"只输出 JSON 数组，不要解释。"
    )


def _build_fields_prompt(chapter: TemplateChapter) -> str:
    """Build prompt for fields type (e.g. cover page)."""
    field_desc = ", ".join(
        f'"{f["key"]}"({f["label"]})' for f in chapter.fields
    )
    return (
        f"章节「{chapter.title}」({chapter.code})，字段类型。\n"
        f"字段：{field_desc}\n\n"
        f"输出格式：JSON 对象，键为字段 key。\n"
        f"只输出 JSON，不要解释。"
    )


def match_chapter_by_title(
    title: str, template: Dict[str, Any]
) -> Optional[TemplateChapter]:
    """Match a section/chapter title to a template chapter by keyword matching.

    Args:
        title: The section title from the source document.
        template: The loaded template dict.

    Returns:
        Best matching TemplateChapter or None.
    """
    from app.services.section_schemas import _SECTION_KEYWORDS

    title_stripped = title.strip()

    # First try exact match on template chapter titles
    for ch_data in template["chapters"]:
        if ch_data["title"] == title_stripped:
            return TemplateChapter.from_dict(ch_data)

    # Keyword-based matching
    # Build keyword lists from template chapter titles
    for ch_data in template["chapters"]:
        ch_title = ch_data["title"]
        # Check if significant portion of title matches
        if len(ch_title) >= 3 and ch_title in title_stripped:
            return TemplateChapter.from_dict(ch_data)
        if len(title_stripped) >= 3 and title_stripped in ch_title:
            return TemplateChapter.from_dict(ch_data)

    # Fallback: use section_schemas keyword matching to find a code mapping
    code_mapping = {
        "file_ref": "G5a",
        "tooling_list": "G10a",
        "tool_gauge": "B12a",
        "material_main": "G12a",
        "material_aux": "G14a",
        "process_flow": "G19a",
        "matching_parts": "G18a",
        "process_card": "G22a",
        "assembly_card": "G25a",
    }

    for section_id, keywords in _SECTION_KEYWORDS:
        for kw in keywords:
            if kw in title_stripped:
                code = code_mapping.get(section_id)
                if code:
                    return get_chapter_by_code(template, code)

    return None
