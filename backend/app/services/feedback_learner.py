"""
FeedbackLearner - Induce readable principles from user edits to AI-generated content.

Takes cell-level diffs (what the user changed after generation) and induces
generalizable rules (e.g. 5x "力矩→扭矩" → one terminology rule). Mirrors the
async + skip_llm + fail-soft pattern of DocumentProfileLearner.

Produced principles carry source="feedback_learned" + enabled=False (pending
review — never auto-pollute generation). Fail-soft: LLM failure degrades to a
deterministic rule-based fallback, never blocks the save that triggered learning.
"""
import json as _json
import re
from collections import Counter
from typing import Any, Dict, List, Tuple

from app.models.profile import Principle
from app.shared.logging import get_logger

logger = get_logger(__name__)

_DIMENSIONS = {"text_compliance", "data_validity", "terminology"}


class FeedbackLearner:
    """Induce principles from user edits to generated content."""

    async def learn_from_edits(
        self,
        edits: List[Dict[str, str]],
        row_changes: List[Dict[str, Any]],
        domain: str = "assembly",
        project_id: str = "",
        skip_llm: bool = False,
    ) -> List[Principle]:
        """Induce principles from user edits. Returns List[Principle] (source=feedback_learned)."""
        if not edits and not row_changes:
            return []

        if skip_llm:
            return self._rule_based_fallback(edits)

        edit_lines = self._format_edits(edits)
        row_lines = self._format_row_changes(row_changes)
        try:
            principles = await self._llm_induce(edit_lines, row_lines, len(edits), len(row_changes))
            if principles:
                logger.info(
                    "feedback_learned_from_llm",
                    domain=domain, rules=len(principles), edits=len(edits),
                )
                return principles
            return self._rule_based_fallback(edits)
        except Exception as e:
            logger.warning("feedback_learn_failed", error=str(e))
            return self._rule_based_fallback(edits)

    # -- formatting ---------------------------------------------------------

    def _format_edits(self, edits: List[Dict[str, str]]) -> str:
        lines = []
        for e in edits:
            col = e.get("col_label") or e.get("col_key", "")
            lines.append(
                f"- 章节[{e.get('section_title', '')}] 行[{e.get('row_key', '')}] "
                f"列[{col}]: 「{e.get('old_value', '')}」→「{e.get('new_value', '')}」"
            )
        return "\n".join(lines)

    def _format_row_changes(self, row_changes: List[Dict[str, Any]]) -> str:
        lines = []
        for r in row_changes:
            row = r.get("row_data", {}) or {}
            preview = ", ".join(f"{k}={v}" for k, v in list(row.items())[:4])
            lines.append(f"- 章节[{r.get('section_title', '')}] {r.get('change', '')}行: {preview}")
        return "\n".join(lines)

    # -- LLM induction ------------------------------------------------------

    async def _llm_induce(
        self, edit_lines: str, row_lines: str, n_edits: int, n_rows: int,
    ) -> List[Principle]:
        """LLM induce generalizable rules from edits. Fail-soft → []."""
        from app.services.llm_service import llm_service

        prompt = (
            "你是工艺文件规则归纳器。下面是用户对 AI 生成结果的修改记录。"
            "请从这些修改中归纳出「用户期望 AI 下次生成时遵守的、人可读的可复用规则」。\n\n"
            f"【单元格修改 ({n_edits} 处)】\n{edit_lines}\n"
        )
        if row_lines:
            prompt += f"\n【行增删 ({n_rows} 处)】\n{row_lines}\n"
        prompt += (
            "\n【归纳要求】\n"
            "1. 只归纳可复用、可泛化的规则，不要逐条复述单次修改。\n"
            "   例：用户把多处「力矩」改成「扭矩」→ 归纳为术语统一规则。\n"
            "   反例：用户把某行数值改成 45 → 这是个例，不归纳。\n"
            "2. 每条规则输出：dimension(text_compliance|data_validity|terminology)、"
            "name(8字内)、description(一句话，描述应怎样写)、check_expression(检查条件)。\n"
            "3. 归纳不出可复用规则时返回 {\"rules\": []}。\n"
            "4. 只输出 JSON：{\"rules\": [{\"dimension\":\"...\",\"name\":\"...\","
            "\"description\":\"...\",\"check_expression\":\"...\"}]}\n"
        )

        resp = await llm_service.generate_with_messages(
            messages=[{"role": "user", "content": prompt}],
            tier="simple", temperature=0.2, max_tokens=600,
        )
        if resp.get("status") != "success":
            return []
        raw = resp.get("content", "").strip()
        m = re.search(r"\{.*\"rules\".*\}", raw, re.DOTALL)
        if not m:
            return []
        try:
            data = _json.loads(m.group())
        except _json.JSONDecodeError:
            return []

        principles: List[Principle] = []
        for rule in data.get("rules", []):
            dim = rule.get("dimension", "terminology")
            if dim not in _DIMENSIONS:
                dim = "terminology"
            principles.append(Principle(
                dimension=dim,
                name=(rule.get("name") or "").strip()[:20],
                description=(rule.get("description") or "").strip(),
                check_expression=(rule.get("check_expression") or "").strip(),
                enabled=False,  # pending review — never auto-pollute generation
                source="feedback_learned",
            ))
        return principles

    # -- deterministic fallback --------------------------------------------

    def _rule_based_fallback(self, edits: List[Dict[str, str]]) -> List[Principle]:
        """Collapse repeated same-column old→new edits into terminology rules.

        Deterministic — guaranteed for the skip_llm test path."""
        if not edits:
            return []
        by_col: Dict[str, List[Tuple[str, str]]] = {}
        for e in edits:
            col = e.get("col_key") or e.get("col_label") or ""
            by_col.setdefault(col, []).append((e.get("old_value", ""), e.get("new_value", "")))

        rules: List[Principle] = []
        for col, pairs in by_col.items():
            (old, new), count = Counter(pairs).most_common(1)[0]
            if count >= 2 and old and new and old != new:
                rules.append(Principle(
                    dimension="terminology",
                    name=f"统一{col}"[:20],
                    description=f"统一使用「{new}」，不使用「{old}」",
                    check_expression=f"检查{col}列是否出现「{old}」，应改为「{new}」",
                    enabled=False,
                    source="feedback_learned",
                ))
        return rules
