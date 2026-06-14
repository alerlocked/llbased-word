"""
Document Chapter Indexer

Parse content.html to build a chapter_index.json mapping QJ 903 table
type codes to page ranges. This provides structural knowledge of the
document so the orchestrator can retrieve full chapter text instead of
keyword fragments.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

from bs4 import BeautifulSoup

from app.shared.logging import get_logger

logger = get_logger(__name__)

# QJ 903 table type code → human-readable chapter title
QJ903_CODE_MAP: Dict[str, str] = {
    "G1a": "封面",
    "G4a": "工艺文件目录",
    "G5a": "引(借)用文件目录",
    "G10a": "专用工艺装备明细表",
    "B12a": "专用工具、量具明细表",
    "G12a": "主要材料消耗工艺定额明细表",
    "G14a": "辅助材料消耗工艺定额明细表",
    "G19a": "工艺流程图",
    "G18a": "配套明细表(表头)",
    "G18b": "配套明细表(内容)",
    "G22a": "工艺过程卡(表头)",
    "G22b": "工艺过程卡(内容)",
    "G25a": "装配工艺卡片(表头)",
    "G25b": "装配工艺卡片(内容)",
}

# Codes that should be merged into a single logical chapter
CODE_GROUP_MAP: Dict[str, str] = {
    "G18a": "配套明细表",
    "G18b": "配套明细表",
    "G22a": "工艺过程卡",
    "G22b": "工艺过程卡",
    "G25a": "装配工艺卡片",
    "G25b": "装配工艺卡片",
}


class DocumentIndexer:
    """Parse content.html and generate chapter_index.json."""

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            from app.config import settings
            self.data_dir = settings.DOCUMENTS_DIR
        else:
            self.data_dir = Path(data_dir)

    def build_index(self, doc_dir_name: str) -> Optional[Dict[str, Any]]:
        """Build chapter index for a document directory.

        Args:
            doc_dir_name: directory name under data_dir (e.g. "1")

        Returns:
            chapter_index dict or None on failure
        """
        doc_dir = self.data_dir / doc_dir_name
        from app.config import settings
        html_path = settings.resolve_doc_content_html(doc_dir)
        index_path = doc_dir / "index.json"

        if not html_path.exists():
            logger.warning("content_html_not_found", path=str(html_path))
            return None

        # Read doc metadata: prefer index.json, fall back to materials table
        doc_name = ""
        total_pages = 0
        if index_path.exists():
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    idx = json.load(f)
                    doc_name = idx.get("name", "")
                    total_pages = idx.get("pages", 0)
            except Exception as e:
                logger.warning("index_read_failed", path=str(index_path), error=str(e))

        # DB fallback for uploaded docs (no index.json): look up material name
        if not doc_name:
            try:
                material_id = int(doc_dir_name)
            except (ValueError, TypeError):
                material_id = None
            if material_id is not None:
                try:
                    from app.database import SessionLocal
                    from app.models.database import Material
                    db = SessionLocal()
                    try:
                        mat = db.query(Material).filter(Material.id == material_id).first()
                        if mat:
                            doc_name = mat.name or ""
                    finally:
                        db.close()
                except Exception as e:
                    logger.warning("material_name_lookup_failed", id=doc_dir_name, error=str(e))

        # Parse content.html → pages with code detection
        pages_data = self._parse_pages(html_path)

        # Build chapters from page code sequence
        chapters = self._build_chapters(pages_data)

        # Update total_pages from actual parse if index was missing it
        if not total_pages and pages_data:
            total_pages = max(p["page_num"] for p in pages_data)

        result = {
            "doc_name": doc_name,
            "total_pages": total_pages,
            "chapters": chapters,
        }

        # Write chapter_index.json
        output_path = doc_dir / "chapter_index.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(
            "chapter_index_built",
            doc_dir=doc_dir_name,
            doc_name=doc_name,
            chapters=len(chapters),
            output=str(output_path),
        )
        return result

    def build_all_indexes(self) -> List[Dict[str, Any]]:
        """Build chapter indexes for all document directories."""
        results = []
        if not self.data_dir.exists():
            return results

        for doc_dir in sorted(self.data_dir.iterdir()):
            if not doc_dir.is_dir():
                continue
            index_path = doc_dir / "index.json"
            if not index_path.exists():
                continue
            result = self.build_index(doc_dir.name)
            if result:
                results.append(result)

        logger.info("all_indexes_built", count=len(results))
        return results

    def _parse_pages(self, html_path: Path) -> List[Dict[str, Any]]:
        """Parse content.html into per-page dicts with code detection.

        Returns:
            List of {"page_num": int, "code": str, "raw_text": str}
        """
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Split by page markers (## 第 N 页)
        # Each page section starts with ## 第 N 页 and ends before the next one
        page_sections = re.split(r"(?=## 第 \d+ 页)", html_content)

        pages_data: List[Dict[str, Any]] = []
        for section in page_sections:
            section = section.strip()
            if not section:
                continue

            # Extract page number
            m = re.match(r"## 第 (\d+) 页", section)
            if not m:
                continue
            page_num = int(m.group(1))

            # Extract QJ 903 code: appears as a standalone token after the page marker
            # Format: "## 第 N 页\n\n<CODE>\n\n<table>..."
            code = self._detect_page_code(section)

            # Strip HTML tags for text content
            soup = BeautifulSoup(section, "html.parser")
            raw_text = soup.get_text(separator="\n")
            # Remove the page marker line itself
            raw_text = re.sub(r"^## 第 \d+ 页\n?", "", raw_text).strip()

            pages_data.append({
                "page_num": page_num,
                "code": code,
                "raw_text": raw_text,
            })

        return pages_data

    def _detect_page_code(self, section: str) -> str:
        """Detect QJ 903 table type code from a page section.

        Codes appear either:
        1. As standalone text between the page marker and first <table>
           (pages 2+: "G4a", "G25a", etc.)
        2. Inside the first <td> of the first <table> on the page
           (page 1 封面: "<td colspan='13'>G1a</td>")
        """
        # Strategy 1: check text before first <table>
        before_table = section.split("<table")[0]
        before_table = re.sub(r"## 第 \d+ 页", "", before_table).strip()

        code = self._match_code_in_text(before_table)
        if code:
            return code

        # Strategy 2: check first <td> content of first <table>
        # Pattern: <td ...>CODE</td>
        td_match = re.search(r"<td[^>]*>([GB]\d+[ab])</td>", section)
        if td_match:
            return td_match.group(1)

        return ""

    def _match_code_in_text(self, text: str) -> str:
        """Match a known QJ 903 code in a text string."""
        all_codes = list(QJ903_CODE_MAP.keys())
        for code in all_codes:
            if re.search(rf"\b{re.escape(code)}\b", text):
                return code
        # Broader pattern for unknown codes
        m = re.search(r"\b([GB]\d+[ab])\b", text)
        if m:
            return m.group(1)
        return ""

    def _build_chapters(self, pages_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group pages into logical chapters based on code sequences.

        Rules:
        - Pages with same code group (e.g. G18a + G18b) merge into one chapter
        - Assembly cards (G25a/G25b) are grouped into sub-chapters per process step
        """
        if not pages_data:
            return []

        chapters: List[Dict[str, Any]] = []
        # First pass: group by logical chapter (using CODE_GROUP_MAP)
        current_chapter: Optional[Dict[str, Any]] = None

        for pd in pages_data:
            page_num = pd["page_num"]
            code = pd["code"]
            raw_text = pd["raw_text"]
            char_count = len(raw_text)

            # Determine the logical group for this code
            group_name = CODE_GROUP_MAP.get(code, None)
            if group_name is None:
                # Single-page chapter (封面, 目录, etc.)
                title = QJ903_CODE_MAP.get(code, code or f"第{page_num}页")
                if current_chapter is not None:
                    chapters.append(current_chapter)
                    current_chapter = None
                chapters.append({
                    "code": code,
                    "title": title,
                    "pages": [page_num],
                    "page_count": 1,
                    "char_count": char_count,
                })
            else:
                # Multi-page chapter group (配套明细表, 工艺过程卡, 装配工艺卡片)
                if current_chapter is None or current_chapter["title"] != group_name:
                    if current_chapter is not None:
                        chapters.append(current_chapter)
                    current_chapter = {
                        "code": code,  # first code in group
                        "title": group_name,
                        "pages": [page_num],
                        "page_count": 1,
                        "char_count": char_count,
                        "sub_chapters": [],
                    }
                else:
                    current_chapter["pages"].append(page_num)
                    current_chapter["page_count"] += 1
                    current_chapter["char_count"] += char_count

        # Save last chapter
        if current_chapter is not None:
            chapters.append(current_chapter)

        # Second pass: for 装配工艺卡片, build sub-chapters (per G25a header page)
        for ch in chapters:
            if ch["title"] == "装配工艺卡片" and len(ch["pages"]) > 2:
                ch["sub_chapters"] = self._build_assembly_sub_chapters(ch, pages_data)

        return chapters

    def _build_assembly_sub_chapters(
        self,
        chapter: Dict[str, Any],
        pages_data: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Split assembly cards into sub-chapters by G25a header pages.

        G25a = header page (starts a new section)
        G25b = continuation page

        Each sub-chapter = one G25a + following G25b pages until next G25a.
        Titles use page ranges to avoid confusion with actual process step numbers.
        """
        # Build a page_num → code lookup
        page_code_map: Dict[int, str] = {}
        # Also build page_num → text for extracting first step name
        page_text_map: Dict[int, str] = {}
        for pd in pages_data:
            page_code_map[pd["page_num"]] = pd["code"]
            page_text_map[pd["page_num"]] = pd["raw_text"]

        sub_chapters: List[Dict[str, Any]] = []
        current_sub: Optional[Dict[str, Any]] = None

        for page_num in chapter["pages"]:
            code = page_code_map.get(page_num, "")

            if code == "G25a":
                # Finalize previous sub-chapter with page-range title
                if current_sub is not None:
                    self._finalize_sub_chapter_title(current_sub, page_text_map)
                    sub_chapters.append(current_sub)
                current_sub = {
                    "title": "",  # filled in _finalize_sub_chapter_title
                    "pages": [page_num],
                    "page_count": 1,
                }
            elif current_sub is not None:
                current_sub["pages"].append(page_num)
                current_sub["page_count"] += 1

        if current_sub is not None:
            self._finalize_sub_chapter_title(current_sub, page_text_map)
            sub_chapters.append(current_sub)

        return sub_chapters

    def _finalize_sub_chapter_title(
        self,
        sub: Dict[str, Any],
        page_text_map: Dict[int, str],
    ) -> None:
        """Set sub-chapter title based on actual content.

        Try to extract the first step description from the G25a page.
        Fall back to page range if no step found.
        """
        first_page = sub["pages"][0]
        first_text = page_text_map.get(first_page, "")

        # Strategy 1: Find a sub-step pattern like "8.1装配隔热套管"
        # OCR text may have no space between step number and Chinese text
        step_match = re.search(
            r"(?:^|\n)\s*(\d+\.\d+)\s*(.{4,30}?)(?:\n|$)",
            first_text,
        )
        if step_match:
            step_num = step_match.group(1)
            step_desc = step_match.group(2).strip()
            sub["title"] = f"第{first_page}页起 ({step_num} {step_desc})"
            return

        # Strategy 2: Find process step in table body (after header rows).
        # G25a table header is typically ~20 lines of column headers.
        # Skip header by looking past "工时定额" or "总计" which mark end of header.
        header_end = first_text.find("工时定额")
        if header_end == -1:
            header_end = first_text.find("总计")
        search_text = first_text[header_end:] if header_end > 0 else first_text

        # Pattern: single/double digit (工序号) | 1-2 char name | Chinese description
        proc_match = re.search(
            r"(?:^|\n)\s*(\d{1,2})\n\s*([\u4e00-\u9fff]{1,4})\n\s*([\u4e00-\u9fff\(（].{2,25}?)(?:\n|$)",
            search_text,
        )
        if proc_match:
            proc_num = proc_match.group(1)
            proc_desc = proc_match.group(3).strip()
            sub["title"] = f"第{first_page}页起 (工序{proc_num} {proc_desc})"
            return

        # Strategy 3: Find any Chinese description line after a single-digit line
        # Simpler fallback for pages with less structured text
        simple_match = re.search(
            r"(?:^|\n)\s*(\d{1,2})\n[^\n]*\n\s*([\u4e00-\u9fff].{4,25}?)(?:\n|$)",
            search_text,
        )
        if simple_match:
            proc_num = simple_match.group(1)
            proc_desc = simple_match.group(2).strip()
            sub["title"] = f"第{first_page}页起 (工序{proc_num} {proc_desc})"
            return

        # Fallback: page range
        pages = sub["pages"]
        if len(pages) == 1:
            sub["title"] = f"第{pages[0]}页"
        else:
            sub["title"] = f"第{pages[0]}-{pages[-1]}页"
