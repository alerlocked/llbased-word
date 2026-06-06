"""
Markdown table parser — extracts structured rows from Markdown tables.

Parses standard Markdown table syntax:
    | Col1 | Col2 | Col3 |
    |------|------|------|
    | val1 | val2 | val3 |

Returns a list of rows (each row is a list of cell strings).
"""
import re
from typing import Dict, List, Optional, Tuple


def parse_markdown_table(text: str) -> List[List[str]]:
    """Parse all Markdown tables in text and return their rows.

    Returns a flat list of rows (header + data rows combined).
    Separator rows (|---|---|) are excluded.
    """
    rows: List[List[str]] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        # Skip separator rows: |---|---|... or | :---: | ---: | ...
        if re.match(r"^\|[\s\-:|]+\|$", stripped):
            continue
        cells = [c.strip() for c in stripped[1:-1].split("|")]
        rows.append(cells)
    return rows


def parse_markdown_tables_by_section(
    text: str,
) -> List[Dict[str, object]]:
    """Parse a multi-section Markdown document into structured sections.

    Sections are delimited by `## Title` headings. Each section may
    contain a table, free text, or both.

    Returns a list of dicts:
        {
            "title": str,
            "content_type": "table" | "text" | "mixed",
            "table_rows": List[List[str]],  # empty if no table
            "table_columns": List[str],      # header row (first row)
            "text_content": str,             # non-table text
        }
    """
    sections: List[Dict[str, object]] = []
    current_title = ""
    current_lines: List[str] = []

    def _flush(title: str, lines: List[str]) -> None:
        if not lines and not title:
            return
        block = "\n".join(lines).strip()
        table_rows = parse_markdown_table(block)

        # Separate table and non-table content
        non_table_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                if re.match(r"^\|[\s\-:|]+\|$", stripped):
                    continue  # separator
                continue  # table data row
            non_table_lines.append(line)

        text_content = "\n".join(non_table_lines).strip()
        table_columns = table_rows[0] if table_rows else []

        if table_rows and text_content:
            content_type = "mixed"
        elif table_rows:
            content_type = "table"
        else:
            content_type = "text"

        sections.append({
            "title": title,
            "content_type": content_type,
            "table_rows": table_rows,
            "table_columns": table_columns,
            "text_content": text_content,
        })

    for line in text.split("\n"):
        # Detect section headings
        heading_match = re.match(r"^##\s+(.+)$", line)
        if heading_match:
            _flush(current_title, current_lines)
            current_title = heading_match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    _flush(current_title, current_lines)
    return sections


def markdown_table_to_html(
    columns: List[str],
    rows: List[List[str]],
) -> str:
    """Convert parsed table data to an HTML table string.

    Args:
        columns: Header column names.
        rows: Data rows (each a list of cell strings).

    Returns:
        HTML string for a <table> element.
    """
    parts = ['<table border="1" cellpadding="4" cellspacing="0">']

    # Header
    parts.append("<thead><tr>")
    for col in columns:
        escaped = col.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        parts.append(f"<th>{escaped}</th>")
    parts.append("</tr></thead>")

    # Body
    parts.append("<tbody>")
    for row in rows:
        parts.append("<tr>")
        col_count = len(columns)
        for i in range(col_count):
            val = row[i] if i < len(row) else ""
            escaped = val.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f"<td>{escaped}</td>")
        parts.append("</tr>")
    parts.append("</tbody>")

    parts.append("</table>")
    return "\n".join(parts)
