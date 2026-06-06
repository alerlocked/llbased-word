"""
Standard Extractor — Extract structured clauses from QJ903 standards.

Reads document.html from QJ903-* directories under DOCUMENTS_DIR, extracts
structured requirements, and persists them into the standards / standard_clauses
tables.

Extraction strategy:
  1. Parse前言 section: extract change descriptions as individual clauses
  2. Parse正文 section: split by section numbers (e.g. 4.2.1) into clauses
  3. Extract applies_to from the standard title (e.g. "装配工艺文件" → assembly)
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from app.shared.logging import get_logger

logger = get_logger(__name__)

# Clause type classification keywords
CLAUSE_TYPE_KEYWORDS = {
    "format": ["格式", "表格", "模板", "编号", "标题", "签字", "页码", "幅面",
               "G1a", "G4a", "G5a", "G10a", "G12a", "G14a", "G19a", "B12a",
               "封面", "主标题栏", "填写"],
    "process": ["工序", "工步", "工艺流程", "操作", "装配", "焊接", "加工", "检验",
                "安装", "编制规则", "工艺总方案"],
    "quality": ["质量", "合格", "缺陷", "偏差", "公差", "验收", "完整性"],
    "safety": ["安全", "防护", "危险", "警告", "禁止", "必须", "应急", "环保"],
}

# Map standard title keywords to applies_to values
TITLE_APPLIES_TO = {
    "总则": "通用",
    "编制一般要求": "通用",
    "封面与主标题栏": "格式",
    "完整性要求": "通用",
    "签署规定": "通用",
    "更改规定": "通用",
    "工艺过程卡片": "工艺过程卡",
    "工艺总方案": "工艺总方案",
    "管理用": "管理文件",
    "消耗工艺定额": "定额文件",
    "编号规定": "通用",
    "机械加工": "机加工艺",
    "钣金": "钣金工艺",
    "热处理": "热处理工艺",
    "铸造": "铸造工艺",
    "锻造": "锻造工艺",
    "焊接": "焊接工艺",
    "装配": "装配工艺",
    "镀覆": "表面处理工艺",
    "电气装配": "电气装配工艺",
    "绕线": "绕线工艺",
    "光学": "光学工艺",
    "推进剂": "推进剂工艺",
}


def _classify_clause(text: str) -> str:
    """Classify a clause into one of the standard types."""
    scores: Dict[str, int] = {}
    for ctype, keywords in CLAUSE_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        scores[ctype] = score
    if not scores or max(scores.values()) == 0:
        return "process"
    return max(scores, key=scores.get)


def _extract_applies_to(title: str) -> Optional[str]:
    """Extract applies_to from standard title."""
    for keyword, applies in TITLE_APPLIES_TO.items():
        if keyword in title:
            return applies
    return None


def _extract_section_number(text: str) -> Optional[str]:
    """Try to extract a section number like '4.2.1' or '5.1' from the start of text."""
    m = re.match(r"^[\s]*(\d+(?:\.\d+)*)", text)
    if m:
        return m.group(1)
    return None


class StandardExtractor:
    """Extract clauses from parsed QJ903 standard documents."""

    def __init__(self, documents_dir: Path | str | None = None):
        if documents_dir is None:
            from app.config import settings
            self._docs_dir = settings.DOCUMENTS_DIR
        else:
            self._docs_dir = Path(documents_dir)

    def list_standards(self) -> List[Dict[str, str]]:
        """List all QJ903 standard document directories."""
        result = []
        for d in sorted(self._docs_dir.iterdir()):
            if not d.is_dir():
                continue
            name = d.name.upper()
            if "QJ903" in name or "QJ 903" in name:
                index_path = d / "index.json"
                idx = {}
                if index_path.exists():
                    try:
                        idx = json.loads(index_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                result.append({
                    "dir_name": d.name,
                    "code": idx.get("standard_code", d.name),
                    "name": idx.get("name", d.name),
                })
        return result

    def extract_standard(self, dir_name: str) -> Dict[str, Any]:
        """Extract clauses from one standard document."""
        doc_dir = self._docs_dir / dir_name
        html_path = self._resolve_html(doc_dir)
        if html_path is None:
            return {"code": dir_name, "title": "", "clauses": []}

        html_content = html_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html_content, "html.parser")
        plain_text = soup.get_text(separator="\n")

        # Read metadata
        index_path = doc_dir / "index.json"
        code = dir_name
        title = ""
        if index_path.exists():
            try:
                idx = json.loads(index_path.read_text(encoding="utf-8"))
                code = idx.get("standard_code", dir_name)
                title = idx.get("name", "")
            except Exception:
                pass

        applies_to = _extract_applies_to(title) if title else None

        clauses = []

        # Strategy 1: Extract change descriptions from 前言
        clauses.extend(self._extract_from_foreword(plain_text, applies_to))

        # Strategy 2: Extract body text by section numbers (for complete standards)
        body_clauses = self._extract_from_body(plain_text, applies_to)
        if body_clauses:
            clauses.extend(body_clauses)

        # Strategy 3: If no clauses found, create an overview clause from the title
        if not clauses and title:
            clauses.append({
                "clause_number": None,
                "requirement": f"标准概述: {title}。本文档为该标准的前言和概述部分。",
                "clause_type": _classify_clause(title),
                "applies_to": applies_to,
            })

        logger.info(f"[标准提取] {code}: {len(clauses)} 条款")
        return {"code": code, "title": title, "clauses": clauses}

    def extract_and_save(self, dir_name: str, db_session) -> Dict[str, int]:
        """Extract from a standard document and persist into DB."""
        from app.models.database import Standard, StandardClause

        data = self.extract_standard(dir_name)

        # Upsert the standard record
        std = db_session.query(Standard).filter_by(code=data["code"]).first()
        if std is None:
            std = Standard(code=data["code"], title=data["title"])
            db_session.add(std)
            db_session.flush()
        else:
            std.title = data["title"]

        # Delete existing clauses for this standard (full refresh)
        db_session.query(StandardClause).filter_by(standard_id=std.id).delete()

        inserted = 0
        for clause_data in data["clauses"]:
            row = StandardClause(
                standard_id=std.id,
                clause_number=clause_data.get("clause_number"),
                requirement=clause_data["requirement"],
                clause_type=clause_data.get("clause_type", "process"),
                applies_to=clause_data.get("applies_to"),
            )
            db_session.add(row)
            inserted += 1

        db_session.commit()
        logger.info(f"[标准提取] 持久化 {data['code']}: {inserted} 条款")
        return {"clauses": inserted}

    def extract_all_standards(self, db_session) -> Dict[str, int]:
        """Extract all QJ903 standards and save to DB."""
        total = {"standards": 0, "clauses": 0}
        for std_info in self.list_standards():
            counts = self.extract_and_save(std_info["dir_name"], db_session)
            total["standards"] += 1
            total["clauses"] += counts["clauses"]
        return total

    # -- internal helpers ----------------------------------------------------

    def _resolve_html(self, doc_dir: Path) -> Optional[Path]:
        for name in ("document.html", "content.html"):
            p = doc_dir / name
            if p.exists():
                return p
        return None

    def _extract_from_foreword(self, text: str, applies_to: Optional[str]) -> List[Dict]:
        """Extract change descriptions from 前言 section.

        Scans the entire document for "——xxx" lines, then filters:
        - Remove directory listings ("第X部分：XXX")
        - Remove self-references ("本部分为/代替")
        - Keep only actual change descriptions
        """
        clauses = []
        lines = text.split("\n")

        for line in lines:
            stripped = line.strip()
            if not (stripped.startswith("——") or stripped.startswith("—")):
                continue

            # Clean up the em-dash prefix
            content = re.sub(r"^[—\-]+\s*", "", stripped)
            if not content or len(content) < 8:
                continue

            # Skip directory listings ("第X部分：XXX")
            if re.match(r"^第\d+部分[：:]", content):
                continue

            # Skip self-references
            if "本部分为" in content or "本部分代替" in content:
                continue

            clauses.append({
                "clause_number": f"前言.{len(clauses) + 1}",
                "requirement": content,
                "clause_type": _classify_clause(content),
                "applies_to": applies_to,
            })

        return clauses

    def _extract_from_body(self, text: str, applies_to: Optional[str]) -> List[Dict]:
        """Extract clauses from body text by section numbering.

        Only used when the document contains actual body content
        (i.e. section numbers like 4.2.1).
        """
        clauses: List[Dict] = []
        lines = text.split("\n")

        current_number = ""
        current_lines: List[str] = []
        found_section = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            section_num = _extract_section_number(stripped)
            if section_num and len(section_num.split(".")) >= 2:
                found_section = True
                # Save previous clause
                if current_lines:
                    requirement = " ".join(current_lines).strip()
                    if len(requirement) > 10:
                        clauses.append({
                            "clause_number": current_number,
                            "requirement": requirement,
                            "clause_type": _classify_clause(requirement),
                            "applies_to": applies_to,
                        })
                current_number = section_num
                rest = stripped[len(section_num):].strip()
                rest = re.sub(r"^[\s.、:：]+", "", rest)
                current_lines = [rest] if rest else []
            elif found_section:
                current_lines.append(stripped)

        # Don't forget the last clause
        if current_lines and found_section:
            requirement = " ".join(current_lines).strip()
            if len(requirement) > 10:
                clauses.append({
                    "clause_number": current_number,
                    "requirement": requirement,
                    "clause_type": _classify_clause(requirement),
                    "applies_to": applies_to,
                })

        return clauses
