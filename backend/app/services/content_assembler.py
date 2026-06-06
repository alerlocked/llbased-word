"""
Content assembler — builds structured JSON v2 and generates HTML from it.

Reads the combined Markdown output from _execute_chapters_parallel and
assembles it into the content.json v2 format (sections with columns/rows).
Then generates content.html for frontend rendering.
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.markdown_table_parser import (
    markdown_table_to_html,
    parse_markdown_table,
    parse_markdown_tables_by_section,
)
from app.services.section_schemas import SectionSchema, match_section_schema


def assemble_content_json(
    combined_markdown: str,
    material_id: str,
    no_source_titles: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Assemble combined Markdown output into content.json v2 format.

    Args:
        combined_markdown: The full Markdown output from chapter parallel generation.
        material_id: The material/document identifier.
        no_source_titles: List of chapter titles that had no reference source.

    Returns:
        A dict matching the content.json v2 schema.
    """
    parsed_sections = parse_markdown_tables_by_section(combined_markdown)
    no_source_set = set(no_source_titles or [])

    sections: List[Dict[str, Any]] = []
    for parsed in parsed_sections:
        title = parsed["title"]
        schema = match_section_schema(title)
        is_no_source = title in no_source_set

        section = _build_section(title, parsed, schema, is_no_source=is_no_source)
        sections.append(section)

    return {
        "version": 2,
        "material_id": material_id,
        "sections": sections,
    }


def _build_section(
    title: str,
    parsed: Dict[str, object],
    schema: Optional[SectionSchema],
    is_no_source: bool = False,
) -> Dict[str, Any]:
    """Build a single section dict from parsed Markdown data."""
    content_type = parsed["content_type"]
    table_rows = parsed.get("table_rows", [])
    table_columns = parsed.get("table_columns", [])
    text_content = parsed.get("text_content", "")

    # Determine content_type from schema if available
    if schema:
        resolved_type = schema.content_type
    elif content_type == "table":
        resolved_type = "table"
    else:
        resolved_type = "text"

    # Determine source tag
    if is_no_source:
        source = "generated_without_reference"
    else:
        source = "generated"

    section: Dict[str, Any] = {
        "section_id": schema.section_id if schema else _title_to_id(title),
        "title": title,
        "content_type": resolved_type,
        "review_passed": True,
        "source": source,
    }

    if resolved_type == "table" and table_rows:
        # Use schema columns if available, otherwise use detected columns
        columns = schema.columns if schema else table_columns
        # Data rows (skip header)
        data_rows = table_rows[1:] if len(table_rows) > 1 else table_rows
        section["columns"] = columns
        section["rows"] = data_rows
    elif resolved_type == "flow_chart":
        section["columns"] = []
        section["rows"] = []
        section["html"] = text_content
    elif resolved_type == "diagram":
        section["columns"] = []
        section["rows"] = []
        section["html"] = text_content
    else:
        # text or mixed
        section["columns"] = []
        section["rows"] = []
        if table_rows:
            section["html"] = markdown_table_to_html(table_columns, table_rows[1:] if len(table_rows) > 1 else [])
            if text_content:
                section["html"] = f"<div>{text_content}</div>\n{section['html']}"
        else:
            section["html"] = text_content

    return section


def _title_to_id(title: str) -> str:
    """Convert a section title to a snake_case section_id."""
    # Remove common punctuation, convert to lowercase snake_case
    slug = re.sub(r"[（）()\s]+", "_", title)
    slug = re.sub(r"[^a-zA-Z0-9_\u4e00-\u9fff]", "", slug)
    slug = slug.strip("_")
    return slug or "unknown"


def generate_content_html(content_json: Dict[str, Any]) -> str:
    """Generate content.html from content.json v2 format.

    Produces an HTML document with each section rendered as a table
    or as free-form HTML content.
    """
    sections = content_json.get("sections", [])
    html_parts = []

    for section in sections:
        title = section.get("title", "")
        content_type = section.get("content_type", "text")

        html_parts.append(f'<div class="section" data-section-id="{section.get("section_id", "")}">')
        html_parts.append(f"<h2>{_esc(title)}</h2>")

        if content_type == "table":
            columns = section.get("columns", [])
            rows = section.get("rows", [])
            if columns:
                html_parts.append(markdown_table_to_html(columns, rows))
        elif content_type in ("flow_chart", "diagram"):
            raw_html = section.get("html", "")
            html_parts.append(f'<div class="{content_type}">{raw_html}</div>')
        else:
            raw_html = section.get("html", "")
            if raw_html:
                html_parts.append(f"<div>{raw_html}</div>")

        html_parts.append("</div>")

    return "\n".join(html_parts)


def save_content_files(
    content_json: Dict[str, Any],
    material_id: str,
    data_dir: str = "backend/data/documents",
) -> Dict[str, str]:
    """Save content.json v2 and content.html to disk.

    Args:
        content_json: The v2 content structure.
        material_id: Document identifier.
        data_dir: Base data directory.

    Returns:
        Dict with paths to saved files.
    """
    doc_dir = Path(data_dir) / material_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    json_path = doc_dir / "content.json"
    html_path = doc_dir / "content.html"

    # Save JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(content_json, f, ensure_ascii=False, indent=2)

    # Generate and save HTML
    html_content = generate_content_html(content_json)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return {
        "json_path": str(json_path),
        "html_path": str(html_path),
    }


def _esc(text: str) -> str:
    """HTML-escape text."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def assemble_from_template(
    template: Dict[str, Any],
    structured_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Assemble content.json v2 from template + structured AI fill results.

    Instead of parsing Markdown, this directly maps template chapters
    and AI-filled JSON data into the content.json v2 schema.

    Args:
        template: Loaded template dict (from template_loader.load_template).
        structured_results: Dict mapping chapter_code to ChapterData-like dict.

    Returns:
        content.json v2 compatible dict.
    """
    from app.services.template_loader import get_editor_chapters

    editor_chapters = get_editor_chapters(template)
    sections: List[Dict[str, Any]] = []

    for chapter in editor_chapters:
        code = chapter.code
        filled = structured_results.get(code)

        if not filled:
            # No data for this chapter — skip or create empty section
            sections.append({
                "section_id": code,
                "title": chapter.title,
                "content_type": _table_type_to_content_type(chapter.table_type),
                "columns": [c.label for c in chapter.columns],
                "rows": [],
                "source": "pending",
                "review_passed": False,
            })
            continue

        content_type = _table_type_to_content_type(chapter.table_type)
        section: Dict[str, Any] = {
            "section_id": code,
            "title": chapter.title,
            "content_type": content_type,
            "review_passed": True,
            "source": "template_generated",
        }

        if chapter.table_type == "dual_list":
            section["left_data"] = filled.get("left_data") or filled.get("left") or []
            section["right_data"] = filled.get("right_data") or filled.get("right") or []
            section["columns"] = [c.label for c in chapter.columns]
            # Extract labels from left/right section column dicts
            left_cols = (chapter.left_section or {}).get("columns", [])
            right_cols = (chapter.right_section or {}).get("columns", [])
            section["left_columns"] = [
                c.get("label", c.get("key", "")) if isinstance(c, dict) else c.label
                for c in left_cols
            ]
            section["right_columns"] = [
                c.get("label", c.get("key", "")) if isinstance(c, dict) else c.label
                for c in right_cols
            ]
        elif chapter.table_type == "flow_chart":
            section["flow_steps"] = filled.get("flow_steps") or []
            section["columns"] = []
            section["rows"] = []
        elif chapter.table_type in ("fields",):
            section["field_values"] = filled.get("field_values") or {}
            section["columns"] = []
            section["rows"] = []
        else:
            # single_row_list, process_card
            section["columns"] = [c.label for c in chapter.columns]
            section["column_keys"] = [c.key for c in chapter.columns]
            section["rows"] = filled.get("filled_data") or []

        sections.append(section)

    return {
        "version": 3,
        "template_id": template.get("template_id", ""),
        "template_name": template.get("template_name", ""),
        "content_format": "template",
        "sections": sections,
    }


def _table_type_to_content_type(table_type: str) -> str:
    """Map template table_type to content.json content_type."""
    mapping = {
        "single_row_list": "table",
        "process_card": "table",
        "dual_list": "dual_table",
        "flow_chart": "flow_chart",
        "fields": "fields",
    }
    return mapping.get(table_type, "text")


# Lazy import helper for TemplateColumn (avoids circular imports)
def _get_template_column_class():
    from app.services.template_types import TemplateColumn
    return TemplateColumn
