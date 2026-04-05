"""
Review Service - 统一审查服务

重构为支持四层检查：
- L1 通用红线
- L2 领域红线
- L3 用户偏好
- 合规性检查
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import yaml
import re
import logging

from app.models.profile import Profile


from app.services.context_service import ContextService


logger = logging.getLogger(__name__)


class CheckType(str, Enum):
    INTENT_CHECK = "intent_check"      # Main Agent 用
    DOCUMENT_CHECK = "document_check"    # Writing Agent 用


class Severity(str, Enum):
    ERROR = "error"        # 错误（阻断性）
    WARNING = "warning"    # 警告
    INFO = "info"          # 信息


    SUGGESTION = "suggestion"  # 建议


@dataclass
class Issue:
    """审查问题"""
    severity: str           # error, warning, info
    type: str             # missing_field, invalid_value, constraint_violation
    field: Optional[str]
    message: str
    location: Optional[str] = None  # 问题位置（段落、行号等）
    hint: Optional[str] = None           # 人类提示
    fix_hint: Optional[str] = None     # Agent 提示
    priority: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "type": self.type,
            "field": self.field,
            "message": self.message,
            "location": self.location,
            "hint": self.hint,
            "fix_hint": self.fix_hint,
            "priority": self.priority
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Issue":
        return cls(
            severity=data.get("severity", "error"),
            type=data.get("type", ""),
            field=data.get("field"),
            message=data.get("message", ""),
            location=data.get("location"),
            hint=data.get("hint"),
            fix_hint=data.get("fix_hint"),
            priority=data.get("priority", 1)
        )


@dataclass
class Suggestion:
    """优化建议"""
    type: str             # improvement, best_practice
    message: str
    priority: str = "medium"  # high, medium, low
    location: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "message": self.message,
            "priority": self.priority,
            "location": self.location
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Suggestion":
        return cls(
            type=data.get("type", "improvement"),
            message=data.get("message", ""),
            priority=data.get("priority", "medium"),
            location=data.get("location")
        )


@dataclass
class ReviewResult:
    """审查结果"""
    passed: bool = True
    score: int = 100
    issues: List[Issue] = field(default_factory=list)
    suggestions: List[Suggestion] = field(default_factory=list)
    
    def add_issue(self, issue: Issue):
        """添加问题"""
        self.issues.append(issue)
        if issue.severity == Severity.ERROR.value:
            self.passed = False
            # 每个错误扣 10 分
            self.score = max(0, self.score - 10)
        elif issue.severity == Severity.WARNING.value:
            # 每个警告扣 3 分
            self.score = max(0, self.score - 3)
    
    def add_suggestion(self, suggestion: Suggestion):
        """添加建议"""
        self.suggestions.append(suggestion)
    
    def calculate_score(self) -> int:
        """
        计算评分
        
        基础分 100
        - 每个 error 扣 10 分
        - 每个 warning 扣 3 分
        
        Returns:
            评分（0-100）
        """
        base_score = 100
        error_count = len([i for i in self.issues if i.severity == Severity.ERROR.value])
        warning_count = len([i for i in self.issues if i.severity == Severity.WARNING.value])
        
        score = base_score - (error_count * 10) - (warning_count * 3)
        return max(0, min(100, score))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "issues": [i.to_dict() for i in self.issues],
            "suggestions": [s.to_dict() for s in self.suggestions]
        }
    
    def to_agent_format(self) -> dict:
        """转换为 Agent 格式 - 结构化，可直接处理"""
        return {
            "passed": self.passed,
            "score": self.score,
            "issues": [
                {
                    "severity": i.severity,
                    "type": i.type,
                    "field": i.field,
                    "message": i.message,
                    "location": i.location,
                    "fix_hint": i.fix_hint
                }
                for i in self.issues
            ],
            "suggestions": [s.to_dict() for s in self.suggestions]
        }
    
    def to_human_format(self) -> str:
        """转换为人类格式 - 人类可读，可直接展示"""
        if self.passed:
            return "✅ 审查通过"
        
        lines = []
        
        # 错误
        errors = [i for i in self.issues if i.severity == Severity.ERROR.value]
        if errors:
            lines.append("❌ 风险/阻断项：")
            for i in errors:
                lines.append(f"  • {i.message}")
                if i.hint:
                    lines.append(f"    💡 {i.hint}")
        
        # 警告
        warnings = [i for i in self.issues if i.severity == Severity.WARNING.value]
        if warnings:
            lines.append("\n⚠️ 警告:")
            for i in warnings:
                lines.append(f"  • {i.message}")
                if i.hint:
                    lines.append(f"    💡 {i.hint}")
        
        # 建议
        if self.suggestions:
            lines.append("\n📝 改进建议:")
            for s in self.suggestions:
                lines.append(f"  • {s.message}")
        
        return "\n".join(lines)


class ReviewService:
    """
    统一审查服务
    
    支持四层检查：
    - L1 通用红线： 所有工艺文件必须遵守的基本规则
    - L2 领域红线： 特定领域（装配/焊接等）的专业规则
    - L3 用户偏好： 从用户画像提取的个性化要求
    - 合规性检查： 法规、安全等合规要求
    """
    
    def __init__(self, context_service: Optional[ContextService] = None):
        """
        初始化审查服务
        
        Args:
            context_service: 上下文服务（用于加载规则和画像）
        """
        self.context_service = context_service or ContextService()
        
        # 规则缓存
        self._l1_rules: Optional[Dict[str, Any]] = None
        self._l2_rules_cache: Dict[str, Dict[str, Any]] = {}
    
        logger.info("review_service_initialized")
    
    # ========================================
    # Main Check API
    # ========================================
    
    def check(
        self,
        content: str,
        domain: str,
        profile: Optional[Profile] = None
    ) -> ReviewResult:
        """
        执行四层检查
        
        Args:
            content: 待审查内容
            domain: 领域
            profile: 用户画像（可选）
            
        Returns:
            ReviewResult: 审查结果
        """
        result = ReviewResult()
        
        # L1 通用红线检查
        l1_issues = self._check_l1_universal(content)
        for issue in l1_issues:
            result.add_issue(issue)
        
        # L2 领域红线检查
        l2_issues = self._check_l2_domain(content, domain)
        for issue in l2_issues:
            result.add_issue(issue)
        
        # L3 用户偏好检查（如果有画像）
        if profile:
            l3_suggestions = self._check_l3_profile(content, profile)
            for suggestion in l3_suggestions:
                result.add_suggestion(suggestion)
        
        # 合规性检查
        compliance_issues = self._check_compliance(content)
        for issue in compliance_issues:
            result.add_issue(issue)
        
        # 重新计算评分
        result.score = result.calculate_score()
        
        logger.info(
            "review_completed",
            passed=result.passed,
            score=result.score,
            issues_count=len(result.issues),
            suggestions_count=len(result.suggestions)
        )
        
        return result
    
    # ========================================
    # L1 通用红线检查
    # ========================================
    
    def _check_l1_universal(self, content: str) -> List[Issue]:
        """
        L1 通用红线检查
        
        检查所有工艺文件必须遵守的基本规则
        
        Args:
            content: 待检查内容
            
        Returns:
            Issue 列表
        """
        issues = []
        
        # 1. 检查必填字段
        required_fields = ["标题", "适用范围", "操作步骤"]
        for field in required_fields:
            if field not in content:
                issues.append(Issue(
                    severity=Severity.ERROR.value,
                    type="missing_field",
                    field=field,
                    message=f"缺少必填字段： {field}",
                    hint=f"请添加 {field} 部分",
                    fix_hint=f"在文档中添加 {field} 部分"
                ))
        
        # 2. 检查格式错误（占位符）
        placeholders = ["TODO", "FIXME", "待补充", "待填写", "XXX"]
        for placeholder in placeholders:
            if placeholder in content:
                issues.append(Issue(
                    severity=Severity.WARNING.value,
                    type="placeholder_found",
                    field=None,
                    message=f"存在占位符: {placeholder}",
                    hint="请补充完整内容",
                    fix_hint=f"替换或删除占位符 {placeholder}"
                ))
        
        # 3. 检查段落结构
        if not re.search(r'^#+\s', content, re.MULTILINE):
            issues.append(Issue(
                severity=Severity.WARNING.value,
                type="missing_structure",
                field=None,
                message="缺少段落标题结构",
                hint="建议使用 Markdown 标题（#）组织内容",
                fix_hint="添加标题结构，如： ## 概述"
            ))
        
        # 4. 检查步骤可执行性
        vague_words = ["适当", "适量", "酌情", "视情况而定"]
        for word in vague_words:
            if word in content:
                issues.append(Issue(
                    severity=Severity.WARNING.value,
                    type="vague_description",
                    message=f"存在模糊描述: {word}",
                    hint="请使用具体数值替代模糊描述",
                    fix_hint=f"将 '{word}' 替换为具体数值"
                ))
        
        return issues
    
    # ========================================
    # L2 领域红线检查
    # ========================================
    
    def _check_l2_domain(self, content: str, domain: str) -> List[Issue]:
        """
        L2 领域红线检查
        
        检查特定领域的专业规则
        
        Args:
            content: 待检查内容
            domain: 领域
            
        Returns:
            Issue 列表
        """
        issues = []
        
        # 加载领域规则
        rules = self._load_l2_rules(domain)
        if not rules:
            return issues
        
        # 装配领域特定检查
        if domain == "assembly":
            issues.extend(self._check_assembly_rules(content))
        # 焊接领域特定检查
        elif domain == "welding":
            issues.extend(self._check_welding_rules(content))
        
        return issues
    
    def _check_assembly_rules(self, content: str) -> List[Issue]:
        """装配领域特定检查"""
        issues = []
        
        # 1. 检查安全措施
        if "安全" not in content and "防护" not in content:
            issues.append(Issue(
                severity=Severity.ERROR.value,
                type="missing_field",
                field="安全措施",
                message="缺少安全措施字段",
                hint="装配工艺必须包含安全措施",
                fix_hint="添加安全措施部分"
            ))
        
        # 2. 检查扭矩值（如果有紧固件）
        if "紧固" in content or "螺栓" in content or "螺钉" in content:
            if "扭矩" not in content and "N·m" not in content:
                issues.append(Issue(
                    severity=Severity.WARNING.value,
                    type="missing_field",
                    field="扭矩值",
                    message="关键紧固件缺少扭矩值",
                    hint="请标注扭矩值，如：XX±XX N·m",
                    fix_hint="在紧固件说明中添加扭矩值"
                ))
        
        return issues
    
    def _check_welding_rules(self, content: str) -> List[Issue]:
        """焊接领域特定检查"""
        issues = []
        
        # 1. 检查焊接参数
        if "焊接" in content:
            required_params = ["电流", "电压", "焊接速度"]
            missing_params = [p for p in required_params if p not in content]
            if missing_params:
                issues.append(Issue(
                    severity=Severity.WARNING.value,
                    type="missing_field",
                    field="焊接参数",
                    message=f"缺少焊接参数: {', '.join(missing_params)}",
                    hint="焊接工艺应包含完整的焊接参数",
                    fix_hint=f"添加焊接参数: {', '.join(missing_params)}"
                ))
        
        # 2. 检查安全措施
        if "安全" not in content:
            issues.append(Issue(
                severity=Severity.ERROR.value,
                type="missing_field",
                field="安全措施",
                message="缺少安全措施字段",
                hint="焊接工艺必须包含安全措施",
                fix_hint="添加安全措施部分"
            ))
        
        return issues
    
    # ========================================
    # L3 用户偏好检查
    # ========================================
    
    def _check_l3_profile(self, content: str, profile: Profile) -> List[Suggestion]:
        """
        L3 用户偏好检查
        
        检查用户个性化的偏好要求
        
        Args:
            content: 待检查内容
            profile: 用户画像
            
        Returns:
            Suggestion 列表
        """
        suggestions = []
        
        # 1. 检查语气偏好
        if profile.writing.tone == "技术文档":
            # 检查是否有口语化表达
            oral_patterns = ["咱们", "你", "搞定", "差不多"]
            for pattern in oral_patterns:
                if pattern in content:
                    suggestions.append(Suggestion(
                        type="tone_mismatch",
                        message="建议使用更正式的语气",
                        priority="medium"
                    ))
                    break
        
        # 2. 检查详细程度偏好
        # 简要模式但内容过长
        if profile.writing.detail_level == "简要":
            # 粗略估计内容长度
            if len(content) > 2000:
                suggestions.append(Suggestion(
                    type="content_length",
                    message="内容较长，建议精简",
                    priority="low"
                ))
        
        # 3. 模板偏差检查
        # TODO: 实现模板偏差计算
        # 比较内容结构与模板结构
        
        return suggestions
    
    # ========================================
    # 合规性检查
    # ========================================
    
    def _check_compliance(self, content: str) -> List[Issue]:
        """
        合规性检查
        
        检查法规、安全等合规要求
        
        Args:
            content: 待检查内容
            
        Returns:
            Issue 列表
        """
        issues = []
        
        # 1. 检查绝对化表述
        absolute_words = ["禁止", "绝对", "严禁", "必须"]
        for word in absolute_words:
            # 查找绝对化表述的上下文
            pattern = rf'{word}[^，。、\s]'
            matches = re.findall(pattern, content)
            for match in matches:
                issues.append(Issue(
                    severity=Severity.WARNING.value,
                    type="absolute_expression",
                    field=None,
                    message=f"包含绝对化表述: {match}",
                    hint="建议使用更严谨的表述",
                    fix_hint=f"修改 '{match}' 为更严谨的表述"
                ))
        
        # 2. 检查安全关键词（高风险作业）
        risk_keywords = ["焊接", "高压", "有毒", "易燃"]
        has_risk = any(kw in content for kw in risk_keywords)
        
        if has_risk:
            # 检查是否有安全提示
            safety_keywords = ["安全", "防护", "注意", "警告"]
            has_safety = any(kw in content for kw in safety_keywords)
            
            if not has_safety:
                issues.append(Issue(
                    severity=Severity.ERROR.value,
                    type="missing_safety",
                    field=None,
                    message="高风险作业缺少安全提示",
                    hint="请添加安全注意事项",
                    fix_hint="在文档中添加安全提示部分"
                ))
        
        return issues
    
    # ========================================
    # Rules Loading
    # ========================================
    
    def _load_l2_rules(self, domain: str) -> Optional[Dict[str, Any]]:
        """加载 L2 领域规则"""
        if domain in self._l2_rules_cache:
            return self._l2_rules_cache[domain]
        
        if self.context_service:
            rules = self.context_service.load_rules("l2", domain)
            self._l2_rules_cache[domain] = rules
            return rules
        
        return None
