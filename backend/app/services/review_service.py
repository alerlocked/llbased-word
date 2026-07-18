"""
Review Service - Unified review engine with principles + preferences.

Checks content against:
- Principles (hard rules): text_compliance, data_validity, terminology
- Preferences (soft rules): readability, executability, style
- Knowledge (condition groups): validate data against known standards
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import re
import json
import logging

from app.models.profile import Profile, ConditionGroup
from app.config import settings

logger = logging.getLogger(__name__)

# Module-level cache for sensitive words (fail-soft: None = not loaded yet)
_sensitive_words_cache: Optional[List[Dict[str, Any]]] = None


def _load_sensitive_words() -> List[Dict[str, Any]]:
    """Load sensitive-word table from DATA_DIR/compliance/sensitive_words.json (cached).

    Fail-soft: file missing / bad JSON → log warning + return [].
    """
    global _sensitive_words_cache
    if _sensitive_words_cache is not None:
        return _sensitive_words_cache

    path = settings.DATA_DIR / "compliance" / "sensitive_words.json"
    try:
        if not path.exists():
            logger.warning("sensitive_words_file_not_found", path=str(path))
            _sensitive_words_cache = []
            return _sensitive_words_cache
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        words = data.get("words", []) if isinstance(data, dict) else []
        _sensitive_words_cache = words if isinstance(words, list) else []
        logger.info("sensitive_words_loaded", count=len(_sensitive_words_cache))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("sensitive_words_load_failed", path=str(path), error=str(e))
        _sensitive_words_cache = []
    return _sensitive_words_cache


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Issue:
    """A review issue found during checking."""
    severity: str
    type: str
    field: Optional[str]
    message: str
    location: Optional[str] = None
    hint: Optional[str] = None
    fix_hint: Optional[str] = None
    principle_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "type": self.type,
            "field": self.field,
            "message": self.message,
            "location": self.location,
            "hint": self.hint,
            "fix_hint": self.fix_hint,
            "principle_id": self.principle_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Issue":
        """Construct an Issue from a dict (inverse of to_dict). Missing optional keys default to None."""
        return cls(
            severity=data["severity"],
            type=data["type"],
            field=data.get("field"),
            message=data["message"],
            location=data.get("location"),
            hint=data.get("hint"),
            fix_hint=data.get("fix_hint"),
            principle_id=data.get("principle_id"),
        )


@dataclass
class ReviewResult:
    """Review result with pass/fail and issues."""
    passed: bool = True
    issues: List[Issue] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)

    def add_issue(self, issue: Issue):
        self.issues.append(issue)
        if issue.severity == Severity.ERROR.value:
            self.passed = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": [i.to_dict() for i in self.issues],
            "suggestions": self.suggestions,
        }


class ReviewService:
    """
    Review engine using profile principles + knowledge + preferences.

    Flow:
    1. Principle checks (hard rules) → Issues (error/warning)
    2. Knowledge validation (condition groups) → Issues for data mismatch
    3. Preference alignment (soft rules) → Suggestions
    """

    async def review(
        self,
        content: str,
        profile: Optional[Profile] = None,
        domain: str = "assembly",
        skip_standard_check: bool = False,
    ) -> ReviewResult:
        """Run full review on content."""
        result = ReviewResult()

        # 1. Hard-coded universal checks (always run)
        self._check_universal(content, result)

        # 1b. Sensitive / vague quantifier checks (profile-independent, runs always)
        # TODO: scope is all "通用" for now; filter by domain once scopes diversify.
        self._check_sensitive_words(content, result)

        # 2. Profile-based principle checks
        if profile:
            self._check_principles(content, profile, result)
            self._check_knowledge_data(content, profile, result)
            # Mandatory quantitative params via LLM (N3). skip_standard_check
            # is reused as the "skip LLM check" switch — no new param added.
            await self._check_mandatory_params(
                content, profile, result, skip_llm=skip_standard_check
            )
            self._check_preferences(content, profile, result)
            # Graph-based structural checks removed (KnowledgeGraph deleted in cleanup)

        logger.info(
            "review_completed",
            passed=result.passed,
            issues=len(result.issues),
            suggestions=len(result.suggestions),
        )
        return result

    # ========================================
    # Universal checks (always run)
    # ========================================

    def _check_universal(self, content: str, result: ReviewResult):
        """Basic checks that apply to all content."""
        # Placeholders
        placeholders = ["TODO", "FIXME", "待补充", "待填写", "XXX"]
        for p in placeholders:
            if p in content:
                result.add_issue(Issue(
                    severity=Severity.WARNING.value,
                    type="placeholder_found",
                    field=None,
                    message=f"存在占位符: {p}",
                    hint="请补充完整内容",
                    fix_hint=f"替换或删除占位符 {p}",
                ))

        # Vague descriptions
        vague_words = ["适当", "适量", "酌情", "视情况而定"]
        for word in vague_words:
            if word in content:
                result.add_issue(Issue(
                    severity=Severity.WARNING.value,
                    type="vague_description",
                    field=None,
                    message=f"存在模糊描述: {word}",
                    fix_hint=f"将 '{word}' 替换为具体数值",
                ))

    def _check_sensitive_words(self, content: str, result: ReviewResult):
        """Detect sensitive / vague quantifiers from sensitive_words.json.

        Match priority: word (full) first, then aliases with length >= 3.
        Short aliases (< 3 chars, e.g. "也可") are skipped to avoid false
        positives on normal sentences.
        """
        words = _load_sensitive_words()
        if not words:
            return
        for entry in words:
            word = entry.get("word", "")
            standard_example = entry.get("standard_example", "")
            matched = False
            if word and word in content:
                matched = True
            if not matched:
                for alias in entry.get("aliases", []) or []:
                    if len(alias) >= 3 and alias in content:
                        matched = True
                        break
            if matched:
                result.add_issue(Issue(
                    severity=Severity.WARNING.value,
                    type="sensitive_word",
                    field=None,
                    message=f"存在敏感词/模糊量词: {word}",
                    hint="建议替换为量化表述",
                    fix_hint=standard_example,
                    principle_id=None,
                ))

    # ========================================
    # Principle checks (from profile)
    # ========================================

    def _check_principles(self, content: str, profile: Profile, result: ReviewResult):
        """Check content against profile principles."""
        for p_dict in profile.principles:
            if not p_dict.get("enabled", True):
                continue

            dimension = p_dict.get("dimension", "")
            check_expr = p_dict.get("check_expression", "")

            if dimension == "text_compliance":
                self._check_text_compliance(content, p_dict, result)
            elif dimension == "data_validity":
                self._check_data_validity(content, p_dict, result)
            elif dimension == "terminology":
                self._check_terminology(content, p_dict, result)

    def _check_text_compliance(self, content: str, principle: Dict, result: ReviewResult):
        """Check text compliance (format, mandatory sections)."""
        name = principle.get("name", "")
        description = principle.get("description", "")
        pid = principle.get("id", "")

        if "章节完整性" in name or "完整性" in name:
            required = ["适用范围", "操作步骤"]
            for r in required:
                if r not in content:
                    result.add_issue(Issue(
                        severity=Severity.ERROR.value,
                        type="missing_field",
                        field=r,
                        message=f"缺少必填字段: {r}",
                        fix_hint=f"在文档中添加 {r} 部分",
                        principle_id=pid,
                    ))

        # Safety check for high-risk operations
        risk_keywords = ["焊接", "高压", "有毒", "易燃"]
        has_risk = any(kw in content for kw in risk_keywords)
        if has_risk:
            safety_keywords = ["安全", "防护", "注意"]
            has_safety = any(kw in content for kw in safety_keywords)
            if not has_safety:
                result.add_issue(Issue(
                    severity="error",
                    type="missing_safety",
                    field=None,
                    message="高风险作业缺少安全提示",
                    fix_hint="在文档中添加安全注意事项",
                    principle_id=pid,
                ))

    def _check_data_validity(self, content: str, principle: Dict, result: ReviewResult):
        """Check data validity against knowledge base condition groups."""
        pid = principle.get("id", "")

        # Check for torque values without units
        torque_pattern = r'(\d+\.?\d*)\s*(?:±\s*(\d+\.?\d*))?\s*(?!N·m|Nm|N\.m|Mpa|MPa)'
        # This regex is too aggressive for now, skip until we have LLM integration

    def _check_terminology(self, content: str, principle: Dict, result: ReviewResult):
        """Check terminology consistency. All principles are hard rules."""
        pid = principle.get("id", "")
        name = principle.get("name", "")

        if "一致性" in name:
            # Basic check: look for common synonym pairs
            synonym_pairs = [
                ("扭矩", "力矩"),
                ("螺栓", "螺钉"),
                ("紧固件", "连接件"),
            ]
            for w1, w2 in synonym_pairs:
                if w1 in content and w2 in content:
                    result.add_issue(Issue(
                        severity=Severity.ERROR.value,
                        type="terminology_inconsistency",
                        field=None,
                        message=f"术语不一致: 同时使用了「{w1}」和「{w2}」",
                        fix_hint=f"统一使用其中一个术语",
                        principle_id=pid,
                    ))

    # ========================================
    # Knowledge-based data validation
    # ========================================

    def _check_knowledge_data(self, content: str, profile: Profile, result: ReviewResult):
        """Validate data in content against condition-grouped knowledge entries."""
        for entry_dict in profile.knowledge:
            cg = ConditionGroup.from_dict(entry_dict)
            entity = cg.entity

            # Check if this entity is mentioned in the content
            if entity not in content:
                continue

            # For each attribute in the knowledge entry, check if the content
            # mentions a value that matches
            for attr_name, attr_value in cg.attributes.items():
                # Look for the attribute value pattern in content near the entity
                # This is a simplified check; LLM-driven check would be more accurate
                if attr_value in content:
                    continue  # Value found, likely correct

                # Check if any value for this attribute is mentioned
                # but doesn't match the expected one
                # (This needs LLM for proper implementation)

    # ========================================
    # Mandatory quantitative params (N3, LLM-driven)
    # ========================================

    async def _check_mandatory_params(
        self,
        content: str,
        profile: Profile,
        result: ReviewResult,
        skip_llm: bool = False,
    ):
        """Check whether the content supplies every REQUIRED quantitative param
        for each profile knowledge entity that the content mentions.

        Fail-soft: any LLM failure (no key / non-success / bad JSON / exception)
        leaves an INFO trace and does NOT block review — i.e. behaves like the
        feature not being installed. The caller's `skip_llm` (reused
        `skip_standard_check`) short-circuits without touching the LLM.
        """
        if skip_llm:
            return

        for entry_dict in profile.knowledge:
            try:
                cg = ConditionGroup.from_dict(entry_dict)
            except Exception as e:
                logger.warning("mandatory_param_entry_parse_failed", error=str(e))
                continue

            # Reuse the entity-hit pattern from _check_knowledge_data
            if cg.entity not in content:
                continue

            required = [
                k for k, v in cg.attributes.items()
                if str(v).startswith("REQUIRED")
            ]
            if not required:
                continue

            await self._llm_check_entity_params(content, cg, required, result)

    async def _llm_check_entity_params(
        self,
        content: str,
        cg: ConditionGroup,
        required: List[str],
        result: ReviewResult,
    ):
        """Call LLM to judge which required params are missing for one entity.

        Fail-soft on every error path — see _check_mandatory_params docstring.
        """
        # Local import avoids a module-load circular dependency
        from app.services.llm_service import llm_service

        entity = cg.entity
        params_list = "、".join(required)
        # Truncate to keep prompt cheap and within context budget
        snippet = content[:1500]

        prompt = (
            "你是工艺文件审校员。判断给定工序内容是否提供了全部必填量化参数的具体数值或范围。\n"
            f"工序：{entity}\n"
            f"必填参数清单：{params_list}\n"
            "判定规则：参数在内容中出现确定数值或区间（如Φ2mm、120A、8～10L/min、15min-20min）"
            "即视为已提供；仅出现参数名而无量值、或完全未提及视为缺失。\n"
            f"待查内容：\n{snippet}\n"
            '示例输出（参数齐全）：{"missing": [], "reason": "三项参数均已给出量值"}\n'
            '示例输出（有缺失）：{"missing": ["焊接电流"], "reason": "仅给钨极直径与气流量，未给电流值"}\n'
            '只输出JSON，不要多余文字。'
        )

        try:
            result_llm = await llm_service.generate_with_messages(
                messages=[{"role": "user", "content": prompt}],
                tier="simple", temperature=0.1, max_tokens=300,
            )
            if result_llm.get("status") != "success":
                result.add_issue(Issue(
                    severity=Severity.INFO.value,
                    type="mandatory_param_check_skipped",
                    field=entity,
                    message=f"必填参数LLM校验跳过: {entity}",
                ))
                logger.warning(
                    "mandatory_param_llm_non_success",
                    entity=entity, status=result_llm.get("status"),
                )
                return

            raw = result_llm.get("content", "").strip()
            missing = self._parse_missing_params(raw)
            if missing is None:
                # JSON unparseable → fail-soft
                result.add_issue(Issue(
                    severity=Severity.INFO.value,
                    type="mandatory_param_check_skipped",
                    field=entity,
                    message=f"必填参数LLM校验跳过: {entity}",
                ))
                logger.warning(
                    "mandatory_param_json_parse_failed",
                    entity=entity, raw=raw[:200],
                )
                return

            for param in missing:
                result.add_issue(Issue(
                    severity=Severity.ERROR.value,
                    type="missing_mandatory_param",
                    field=entity,
                    message=f"工序「{entity}」缺失必填参数: {param}",
                    hint="按实施细则补充量化值",
                    fix_hint=str(cg.attributes.get(param, "")),
                    principle_id=None,
                ))
        except Exception as e:
            # Last-resort fail-soft: never let LLM plumbing break review
            result.add_issue(Issue(
                severity=Severity.INFO.value,
                type="mandatory_param_check_skipped",
                field=entity,
                message=f"必填参数LLM校验跳过: {entity}",
            ))
            logger.warning(
                "mandatory_param_check_failed", entity=entity, error=str(e),
            )

    @staticmethod
    def _parse_missing_params(raw: str) -> Optional[List[str]]:
        """Extract the 'missing' array from an LLM JSON response.

        Tolerates surrounding prose / fenced code blocks. Returns None if no
        valid JSON object can be recovered (signals fail-soft upstream).
        """
        if not raw:
            return None
        candidate = raw
        # Strip ```json ... ``` fences if present
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if fence:
            candidate = fence.group(1)
        else:
            obj = re.search(r"\{.*\}", raw, re.DOTALL)
            if obj:
                candidate = obj.group(0)
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            return None
        missing = data.get("missing") if isinstance(data, dict) else None
        if not isinstance(missing, list):
            return None
        return [str(m).strip() for m in missing if str(m).strip()]

    # ========================================
    # Preference alignment
    # ========================================

    def _check_preferences(self, content: str, profile: Profile, result: ReviewResult):
        """Generate suggestions based on learned preferences."""
        if profile.writing.tone == "技术文档":
            oral_patterns = ["咱们", "搞定", "差不多"]
            for pattern in oral_patterns:
                if pattern in content:
                    result.suggestions.append({
                        "type": "tone_mismatch",
                        "message": f"建议使用更正式的表述，当前语调偏好为「技术文档」",
                        "location": pattern,
                    })
                    break

        # Check against learned preferences
        for pref_dict in profile.preferences_list:
            dimension = pref_dict.get("dimension", "")
            if dimension == "style":
                # Check negative examples
                for neg in pref_dict.get("negative_examples", []):
                    if neg in content:
                        result.suggestions.append({
                            "type": "style_preference",
                            "message": f"已学习的偏好不建议使用: 「{neg}」",
                            "preference_id": pref_dict.get("id"),
                        })

    # ========================================
    # Graph-based structural checks (removed — KnowledgeGraph deleted in cleanup)
    # ========================================

