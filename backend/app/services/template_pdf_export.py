"""
Template PDF export service.

Renders a complete PDF from template structure + filled values + footer fields.
Uses HTML → PDF conversion (WeasyPrint or similar).
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.shared.logging import get_logger

logger = get_logger(__name__)


def export_template_pdf(
    template: Dict[str, Any],
    structured_doc: Dict[str, Any],
    footer_values: Dict[str, Any],
    output_path: str,
) -> str:
    """Export a complete PDF from template + structured data.

    Renders: cover page + all chapters + footer (signatures).

    Args:
        template: Loaded template dict.
        structured_doc: StructuredDocument.to_dict() output.
        footer_values: Key-value pairs for footer fields.
        output_path: Where to save the PDF.

    Returns:
        Path to the generated PDF file.
    """
    html = render_full_html(template, structured_doc, footer_values)

    # Save intermediate HTML for debugging
    html_path = Path(output_path).with_suffix(".html")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    # Convert HTML to PDF
    try:
        from weasyprint import HTML as WeasyHTML

        WeasyHTML(string=html).write_pdf(output_path)
        logger.info("template_pdf_exported", output_path=output_path)
        return output_path
    except ImportError:
        logger.warning("weasyprint_not_available, returning HTML instead")
        return str(html_path)
    except Exception as e:
        logger.error("pdf_export_failed", error=str(e))
        raise


def render_full_html(
    template: Dict[str, Any],
    structured_doc: Dict[str, Any],
    footer_values: Dict[str, Any],
) -> str:
    """Render complete HTML document for PDF export.

    Includes cover page, all chapters as tables, and footer signature area.
    """
    chapters = structured_doc.get("chapters", [])
    chapter_order = template.get("chapter_order", [])

    # Sort chapters by template order
    ordered = _sort_chapters(chapters, chapter_order)

    parts: List[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append("<html><head>")
    parts.append(_get_pdf_styles())
    parts.append("</head><body>")

    for ch in ordered:
        parts.append(_render_chapter_html(ch, template))

    # Footer signature area
    parts.append(_render_footer(footer_values, template))

    parts.append("</body></html>")
    return "\n".join(parts)


def _sort_chapters(
    chapters: List[Dict[str, Any]], order: List[str]
) -> List[Dict[str, Any]]:
    """Sort chapters by template's chapter_order."""
    code_order = {code: idx for idx, code in enumerate(order)}
    return sorted(chapters, key=lambda ch: code_order.get(ch.get("chapter_code", ""), 99))


def _render_chapter_html(chapter: Dict[str, Any], template: Dict[str, Any]) -> str:
    """Render a single chapter as HTML."""
    code = chapter.get("chapter_code", "")
    title = chapter.get("chapter_title", "")
    table_type = chapter.get("table_type", "")
    parts: List[str] = []

    parts.append(f'<div class="chapter" data-code="{_esc(code)}">')
    parts.append(f"<h2>{_esc(title)}</h2>")

    if table_type == "flow_chart":
        steps = chapter.get("flow_steps") or []
        if steps:
            parts.append('<ol class="flow-steps">')
            for step in steps:
                parts.append(f"<li>{_esc(str(step))}</li>")
            parts.append("</ol>")

    elif table_type == "dual_list":
        left = chapter.get("left_data") or []
        right = chapter.get("right_data") or []
        tmpl_ch = _find_template_chapter(template, code)
        left_cols = (tmpl_ch.get("left_section", {}) or {}).get("columns", []) if tmpl_ch else []
        right_cols = (tmpl_ch.get("right_section", {}) or {}).get("columns", []) if tmpl_ch else []

        parts.append('<div class="dual-table">')
        parts.append('<div class="dual-half">')
        parts.append(_render_table(left_cols, left))
        parts.append("</div>")
        parts.append('<div class="dual-half">')
        parts.append(_render_table(right_cols, right))
        parts.append("</div>")
        parts.append("</div>")

    elif table_type == "fields":
        field_values = chapter.get("field_values") or {}
        if field_values:
            parts.append('<table class="fields-table">')
            for key, val in field_values.items():
                parts.append(f"<tr><th>{_esc(str(key))}</th><td>{_esc(str(val))}</td></tr>")
            parts.append("</table>")

    else:
        # single_row_list or process_card
        tmpl_ch = _find_template_chapter(template, code)
        columns = tmpl_ch.get("columns", []) if tmpl_ch else []
        rows = chapter.get("filled_data") or []
        parts.append(_render_table(columns, rows))

    parts.append("</div>")
    return "\n".join(parts)


def _render_table(
    columns: List[Dict[str, Any]], rows: List[Dict[str, Any]]
) -> str:
    """Render columns + rows as an HTML table."""
    if not columns and not rows:
        return "<p>（空）</p>"

    parts: List[str] = []
    parts.append('<table class="data-table">')

    # Header
    parts.append("<thead><tr>")
    for col in columns:
        label = col.get("label", col.get("key", "")) if isinstance(col, dict) else str(col)
        parts.append(f"<th>{_esc(str(label))}</th>")
    parts.append("</tr></thead>")

    # Rows
    if rows:
        parts.append("<tbody>")
        for row in rows:
            parts.append("<tr>")
            for col in columns:
                key = col.get("key", "") if isinstance(col, dict) else str(col)
                val = row.get(key, "") if isinstance(row, dict) else ""
                parts.append(f"<td>{_esc(str(val))}</td>")
            parts.append("</tr>")
        parts.append("</tbody>")

    parts.append("</table>")
    return "\n".join(parts)


def _render_footer(
    footer_values: Dict[str, Any], template: Dict[str, Any]
) -> str:
    """Render footer signature area."""
    footer_fields = template.get("footer_fields", {})
    fields = footer_fields.get("fields", []) if isinstance(footer_fields, dict) else []

    if not fields:
        return ""

    parts: List[str] = []
    parts.append('<div class="footer-signatures">')
    parts.append("<table><tr>")

    for field in fields:
        key = field.get("key", "")
        label = field.get("label", "")
        value = footer_values.get(key, field.get("default", ""))
        parts.append(
            f'<td class="sig-cell">'
            f'<div class="sig-label">{_esc(label)}</div>'
            f'<div class="sig-value">{_esc(str(value))}</div>'
            f"</td>"
        )

    parts.append("</tr></table>")
    parts.append("</div>")
    return "\n".join(parts)


def _find_template_chapter(template: Dict[str, Any], code: str) -> Optional[Dict[str, Any]]:
    """Find a chapter definition in the template by code."""
    for ch in template.get("chapters", []):
        if ch.get("code") == code:
            return ch
    return None


def _get_pdf_styles() -> str:
    """Return CSS styles for PDF rendering."""
    return """<style>
    @page { size: A4; margin: 20mm 15mm; }
    body { font-family: "SimSun", "Noto Sans CJK SC", serif; font-size: 12pt; line-height: 1.6; color: #000; }
    h1 { font-size: 18pt; text-align: center; margin: 20pt 0; }
    h2 { font-size: 14pt; margin: 16pt 0 8pt; border-bottom: 1pt solid #333; padding-bottom: 4pt; }
    .chapter { page-break-after: always; }
    .chapter:last-child { page-break-after: auto; }
    .data-table { width: 100%; border-collapse: collapse; margin: 8pt 0; }
    .data-table th, .data-table td { border: 1pt solid #333; padding: 4pt 8pt; text-align: left; font-size: 10pt; }
    .data-table th { background-color: #f0f0f0; font-weight: bold; }
    .fields-table { width: 60%; border-collapse: collapse; margin: 8pt auto; }
    .fields-table th, .fields-table td { border: 1pt solid #999; padding: 6pt 12pt; }
    .fields-table th { text-align: right; width: 40%; background-color: #f5f5f5; }
    .dual-table { display: flex; gap: 12pt; }
    .dual-half { flex: 1; }
    .flow-steps { padding-left: 24pt; }
    .flow-steps li { margin: 4pt 0; }
    .footer-signatures { margin-top: 20pt; border-top: 1pt solid #333; padding-top: 8pt; }
    .footer-signatures table { width: 100%; }
    .sig-cell { text-align: center; padding: 6pt; }
    .sig-label { font-size: 10pt; color: #666; }
    .sig-value { font-size: 12pt; min-height: 20pt; border-bottom: 1pt solid #ccc; }
    </style>"""


def _esc(text: str) -> str:
    """HTML-escape text."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
