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
import logging

from app.models.profile import Profile, ConditionGroup

logger = logging.getLogger(__name__)


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

    def review(
        self,
        content: str,
        profile: Optional[Profile] = None,
        domain: str = "assembly",
    ) -> ReviewResult:
        """Run full review on content."""
        result = ReviewResult()

        # 1. Hard-coded universal checks (always run)
        self._check_universal(content, result)

        # 2. Profile-based principle checks
        if profile:
            self._check_principles(content, profile, result)
            self._check_knowledge_data(content, profile, result)
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

