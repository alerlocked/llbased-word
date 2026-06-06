"""
Section schema definitions for structured process document generation.

Each section type defines the expected output format (table, flow_chart, diagram,
text) and, for table types, the exact columns the LLM must produce.

Title matching uses keyword-based heuristics so that chapter titles from VLM
extraction (which may vary slightly) map to the correct schema.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SectionSchema:
    """Template definition for one section of a process document."""
    section_id: str
    title: str
    content_type: str  # table | flow_chart | diagram | text
    columns: List[str] = field(default_factory=list)
    required_columns: List[str] = field(default_factory=list)
    description: str = ""


# ---------------------------------------------------------------------------
# A. Section schema registry — 10 standard QJ903 sections
# ---------------------------------------------------------------------------

SECTION_SCHEMAS: Dict[str, SectionSchema] = {
    "file_ref": SectionSchema(
        section_id="file_ref",
        title="引用文件目录",
        content_type="table",
        columns=["序号", "代号", "文件名称", "页数", "备注"],
        required_columns=["序号", "文件名称"],
        description="引(借)用文件目录",
    ),
    "tooling_list": SectionSchema(
        section_id="tooling_list",
        title="专用工艺装备明细表",
        content_type="table",
        columns=["序号", "编号", "名称", "类别", "数量", "用于代号", "用于名称", "使用单位", "备注"],
        required_columns=["序号", "名称"],
        description="专用工艺装备明细表",
    ),
    "tool_gauge": SectionSchema(
        section_id="tool_gauge",
        title="专用工具量具明细表",
        content_type="table",
        columns=["序号", "名称", "型号或规格", "数量", "备注"],
        required_columns=["序号", "名称"],
        description="专用工具量具明细表",
    ),
    "material_main": SectionSchema(
        section_id="material_main",
        title="主要材料消耗工艺定额明细表",
        content_type="table",
        columns=["序号", "零件代号", "零件名称", "材料名称牌号", "计量单位", "单套数量", "本批数量"],
        required_columns=["序号", "材料名称牌号"],
        description="主要材料消耗工艺定额明细表",
    ),
    "material_aux": SectionSchema(
        section_id="material_aux",
        title="辅助材料消耗工艺定额明细表",
        content_type="table",
        columns=["序号", "材料名称牌号", "计量单位", "单套数量", "本批数量", "备注"],
        required_columns=["序号", "材料名称牌号"],
        description="辅助材料消耗工艺定额明细表",
    ),
    "process_flow": SectionSchema(
        section_id="process_flow",
        title="工艺流程图",
        content_type="flow_chart",
        description="工艺流程图（保留原始结构）",
    ),
    "matching_parts": SectionSchema(
        section_id="matching_parts",
        title="配套明细表",
        content_type="table",
        columns=["序号", "代号", "名称", "数量", "来自何处", "备注"],
        required_columns=["序号", "名称"],
        description="配套明细表",
    ),
    "process_card": SectionSchema(
        section_id="process_card",
        title="工艺过程卡",
        content_type="table",
        columns=["工序号", "工序名称", "工序内容简述", "设备", "工艺装备", "工时定额"],
        required_columns=["工序号", "工序名称"],
        description="工艺过程卡",
    ),
    "assembly_card": SectionSchema(
        section_id="assembly_card",
        title="装配工艺卡片",
        content_type="table",
        columns=["工序号", "工序名称", "工序内容简述", "设备", "工艺装备", "工时定额"],
        required_columns=["工序号", "工序名称"],
        description="装配工艺卡片",
    ),
    "diagrams": SectionSchema(
        section_id="diagrams",
        title="工艺简图",
        content_type="diagram",
        description="工艺简图（保留原始图示）",
    ),
}


# ---------------------------------------------------------------------------
# B. Title matching — keyword heuristics for chapter → schema mapping
# ---------------------------------------------------------------------------

# Keywords that strongly indicate a section type.
# Each entry: (section_id, list of keywords that must appear in the title)
_SECTION_KEYWORDS: List[tuple] = [
    ("file_ref", ["引用", "借用", "文件目录"]),
    ("tooling_list", ["工艺装备", "工装明细"]),
    ("tool_gauge", ["工具量具", "量具明细"]),
    ("material_main", ["主要材料"]),
    ("material_aux", ["辅助材料"]),
    ("process_flow", ["工艺流程", "流程图"]),
    ("matching_parts", ["配套明细", "配套表"]),
    ("process_card", ["工艺过程"]),
    ("assembly_card", ["装配工艺"]),
    ("diagrams", ["工艺简图"]),
]


def match_section_schema(chapter_title: str) -> Optional[SectionSchema]:
    """Match a chapter title to the best SectionSchema.

    Uses keyword matching with priority ordering. Returns None if no
    schema matches — these chapters are handled as free-text.
    """
    title_lower = chapter_title.strip()

    for section_id, keywords in _SECTION_KEYWORDS:
        for kw in keywords:
            if kw in title_lower:
                return SECTION_SCHEMAS[section_id]

    return None


def build_schema_prompt(schema: SectionSchema) -> str:
    """Build a prompt fragment that constrains LLM output to a schema.

    For table-type schemas, this produces a column template instruction.
    For non-table types, it returns a brief format note.
    """
    if schema.content_type != "table":
        return (
            f"该章节类型为「{schema.content_type}」，请保持原有结构格式输出。"
        )

    col_header = " | ".join(schema.columns)
    col_sep = " | ".join("---" for _ in schema.columns)
    example_row = " | ".join("..." for _ in schema.columns)

    return (
        f"\n\n输出格式（硬约束）：\n"
        f"| {col_header} |\n"
        f"| {col_sep} |\n"
        f"| {example_row} |\n\n"
        f"固定 {len(schema.columns)} 列，不要增加或减少列。"
        f"每行对应一条数据记录。\n"
        f"必填列：{'、'.join(schema.required_columns)}，不得为空。"
    )
