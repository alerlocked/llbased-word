"""
Template type definitions for structured document generation.

Data classes for template chapters, columns, and structured output.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TemplateColumn:
    """A single column definition in a template chapter."""
    key: str
    label: str
    col_type: str = "text"  # text | number | long_text | select | ordered_list
    required: bool = False
    ai_filled: bool = False
    default: Optional[str] = None
    options: Optional[List[str]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemplateColumn":
        return cls(
            key=data["key"],
            label=data["label"],
            col_type=data.get("type", "text"),
            required=data.get("required", False),
            ai_filled=data.get("ai_filled", False),
            default=data.get("default"),
            options=data.get("options"),
        )


@dataclass
class TemplateChapter:
    """A chapter definition from the template JSON."""
    code: str
    title: str
    table_type: str  # single_row_list | process_card | dual_list | flow_chart | fields
    columns: List[TemplateColumn] = field(default_factory=list)
    editor_visible: bool = True
    pages: Any = 1  # int or "variable"
    ai_guidance: str = ""
    header_extra: List[Dict[str, Any]] = field(default_factory=list)
    sub_sections: List[Dict[str, Any]] = field(default_factory=list)
    left_section: Optional[Dict[str, Any]] = None
    right_section: Optional[Dict[str, Any]] = None
    fields: List[Dict[str, Any]] = field(default_factory=list)
    continuation_code: Optional[str] = None
    continuation_title: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemplateChapter":
        columns = [TemplateColumn.from_dict(c) for c in data.get("columns", [])]
        return cls(
            code=data["code"],
            title=data["title"],
            table_type=data.get("table_type", "fields"),
            columns=columns,
            editor_visible=data.get("editor_visible", True),
            pages=data.get("pages", 1),
            ai_guidance=data.get("ai_guidance", ""),
            header_extra=data.get("header_extra", []),
            sub_sections=data.get("sub_sections", []),
            left_section=data.get("left_section"),
            right_section=data.get("right_section"),
            fields=data.get("fields", []),
            continuation_code=data.get("continuation_code"),
            continuation_title=data.get("continuation_title"),
        )


@dataclass
class ChapterData:
    """Filled data for one chapter, produced by WritingAgent._do_template_fill."""
    chapter_code: str
    chapter_title: str
    table_type: str
    filled_data: List[Dict[str, Any]] = field(default_factory=list)
    # For dual_list type
    left_data: Optional[List[Dict[str, Any]]] = None
    right_data: Optional[List[Dict[str, Any]]] = None
    # For flow_chart type
    flow_steps: Optional[List[str]] = None
    # For fields type (cover page)
    field_values: Optional[Dict[str, Any]] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class StructuredDocument:
    """Complete structured document produced by template-driven generation."""
    template_id: str
    template_name: str
    chapters: List[ChapterData] = field(default_factory=list)
    footer_values: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_name": self.template_name,
            "chapters": [
                {
                    "chapter_code": ch.chapter_code,
                    "chapter_title": ch.chapter_title,
                    "table_type": ch.table_type,
                    "filled_data": ch.filled_data,
                    "left_data": ch.left_data,
                    "right_data": ch.right_data,
                    "flow_steps": ch.flow_steps,
                    "field_values": ch.field_values,
                }
                for ch in self.chapters
            ],
            "footer_values": self.footer_values,
        }
