"""Review pipeline: four-way factual check for dialog review questions.

Design principle (user rule): the TEMPLATE is the only judge of "what a
complete document is" — never the LLM's general knowledge. Checks 1-3 are
deterministic and machine-computed into a fact list; the LLM only does check 4
(requirement coverage) and may ONLY reference the fact list.

Checks:
  1. template  — template chapter codes − generated chapter codes = missing
  2. db        — material names/standard codes in generated content vs
                 MaterialCatalog (grounded / no-record), info-level
  3. quality   — empty cells / 待补 placeholders / degraded warnings
  4. coverage  — user's original request vs the fact list (LLM, simple tier,
                 hard-constrained to cite facts only)
"""
import re
from typing import Any, Dict, List, Optional

from app.shared.logging import get_logger

logger = get_logger(__name__)

_MAX_DB_LOOKUPS = 20  # cap DB grounding checks per review (latency guard)
_PLACEHOLDER = re.compile(r"^\s*(待补|待确认)?$")

# Material-ish columns to ground-check (name-ish keys)
_MATERIAL_KEYS = ("material", "材料", "part_name", "名称", "name", "辅材")
_CODE_KEYS = ("standard_code", "part_code", "代号", "code", "标准号")


def _check_template(template_id: str, structured_results: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Check 1: template chapter codes − generated codes = missing chapters."""
    issues: List[Dict[str, Any]] = []
    try:
        from app.services.template_loader import load_template, get_chapters

        chapters = get_chapters(load_template(template_id))
    except Exception as e:
        logger.warning("review_template_load_failed", template_id=template_id, error=str(e))
        return []
    generated = set(structured_results or {})
    for ch in chapters:
        if ch.code not in generated:
            issues.append({
                "severity": "critical",
                "source": "template",
                "message": f"缺章：{ch.code}（{ch.title}）未生成——模板要求章节",
            })
    if not issues:
        issues.append({
            "severity": "info",
            "source": "template",
            "message": f"模板 {len(chapters)} 章对照完成，无缺章",
        })
    return issues


def _check_quality(structured_results: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Check 3: empty cells / placeholders / per-row warnings in generated chapters."""
    issues: List[Dict[str, Any]] = []
    for code, data in (structured_results or {}).items():
        if not isinstance(data, dict):
            continue
        rows = data.get("filled_data") or []
        empty_cells = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            for k, v in row.items():
                if isinstance(v, str) and _PLACEHOLDER.match(v):
                    empty_cells += 1
        if empty_cells:
            issues.append({
                "severity": "warn",
                "source": "quality",
                "message": f"{code} 有 {empty_cells} 个空/待补格子",
            })
        for w in data.get("warnings") or []:
            issues.append({
                "severity": "warn",
                "source": "quality",
                "message": f"{code} {w.get('message', '生成告警')}",
            })
    if not issues:
        issues.append({"severity": "info", "source": "quality", "message": "已生成章节无空格/告警"})
    return issues


def _check_db(structured_results: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Check 2: material names / standard codes vs MaterialCatalog (grounded?)."""
    issues: List[Dict[str, Any]] = []
    names: List[str] = []
    for data in (structured_results or {}).values():
        if not isinstance(data, dict):
            continue
        for row in data.get("filled_data") or []:
            if not isinstance(row, dict):
                continue
            for k, v in row.items():
                if any(mk in str(k) for mk in _MATERIAL_KEYS) and isinstance(v, str) and v.strip():
                    names.append(v.strip())
    # dedupe, cap
    seen = set()
    unique = [n for n in names if not (n in seen or seen.add(n))][:_MAX_DB_LOOKUPS]
    if not unique:
        return []
    truncated = len(names) > _MAX_DB_LOOKUPS
    try:
        from app.database import SessionLocal
        from app.models.database import MaterialCatalog
        from app.services.knowledge_search import KnowledgeSearchService

        svc = KnowledgeSearchService()
        db = SessionLocal()
        try:
            no_record = []
            for name in unique:
                hit = db.query(MaterialCatalog).filter(
                    MaterialCatalog.name == name
                ).first()
                if not hit:
                    hit = db.query(MaterialCatalog).filter(
                        MaterialCatalog.name.like(f"%{name}%")
                    ).first()
                if not hit:
                    no_record.append(name)
        finally:
            db.close()
        if no_record:
            issues.append({
                "severity": "info",
                "source": "db",
                "message": (
                    f"材料目录无记录（{len(no_record)} 项）：{'、'.join(no_record[:5])}"
                    + ("…" if len(no_record) > 5 else "")
                    + ("（超过核对上限，部分核对）" if truncated else "")
                ),
            })
        else:
            issues.append({
                "severity": "info",
                "source": "db",
                "message": f"材料目录核对 {len(unique)} 项全部有据" + ("（超上限部分核对）" if truncated else ""),
            })
    except Exception as e:
        logger.warning("review_db_check_failed", error=str(e))
    return issues


async def _check_coverage(user_input: str, fact_lines: List[str]) -> str:
    """Check 4 (only LLM): requirement coverage — may ONLY cite the fact list."""
    from app.services.llm_service import llm_service

    prompt = (
        "你是工艺文件审查助手。下面是机器对照产出的事实清单。"
        "你的唯一任务：结合用户的原始需求，把事实清单组织成对用户问题的直接回答。\n"
        "硬约束：\n"
        "1. 只能引用事实清单里的内容，禁止基于通识/常识补充评估\n"
        "2. 事实清单没有覆盖的方面，明说\"清单未覆盖\"，不许编\n"
        "3. 简明扼要，中文，直接回答问题\n\n"
        f"用户问题：{user_input[:300]}\n\n"
        "事实清单：\n" + "\n".join(f"- {l}" for l in fact_lines[:60]) + "\n"
    )
    try:
        result = await llm_service.generate_with_messages(
            messages=[{"role": "user", "content": prompt}],
            tier="simple", temperature=0.2, max_tokens=600,
        )
        if result.get("status") == "success" and result.get("content"):
            return result["content"].strip()
        logger.warning("review_coverage_llm_failed", status=result.get("status"))
        return "需求对照未完成（模型暂不可用），以上为机器对照结果。"
    except Exception as e:
        logger.warning("review_coverage_llm_error", error=str(e))
        return "需求对照未完成（模型异常），以上为机器对照结果。"


def render_issues(issues: List[Dict[str, Any]]) -> str:
    """Render the issue list as a readable chat reply (graded, sourced)."""
    order = {"critical": 0, "warn": 1, "info": 2}
    label = {"critical": "🔴", "warn": "🟡", "info": "⚪"}
    lines = ["📋 审查结果（基于模板与生成内容对照）：", ""]
    for issue in sorted(issues, key=lambda i: order.get(i.get("severity"), 3)):
        lines.append(f"{label.get(issue['severity'], '⚪')} {issue['message']}（{issue['source']}）")
    return "\n".join(lines)


async def run_review(
    user_input: str,
    project_state: Optional[Dict[str, Any]] = None,
    structured_results: Optional[Dict[str, Any]] = None,
    template_id: str = "assembly_process_cable",
) -> Dict[str, Any]:
    """Entry: four-way review. Returns {"issues": [...], "reply": str}.

    structured_results: full generated output if available; else falls back
    to the project state's last_output snapshot (summary level — template
    check still works off chapter codes; quality/db checks degrade to info).
    """
    if not structured_results:
        lo = ((project_state or {}).get("outputs") or {}).get("generated") or {}
        snapshot_codes = {c.get("code") for c in lo.get("chapters", []) if c.get("code")}
        structured_results = {code: {"chapter_title": "", "filled_data": []} for code in snapshot_codes}

    issues: List[Dict[str, Any]] = []
    issues.extend(_check_template(template_id, structured_results))
    issues.extend(_check_quality(structured_results))
    issues.extend(_check_db(structured_results))

    fact_lines = [i["message"] for i in issues]
    coverage = await _check_coverage(user_input, fact_lines)

    reply = render_issues(issues) + "\n\n" + coverage
    return {"issues": issues, "reply": reply}
