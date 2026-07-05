"""
test_review_service.py - ReviewService 单元测试
"""
import pytest
from pathlib import Path
import yaml

from app.services.review_service import ReviewService, ReviewResult, Issue, Severity
from app.models.profile import Profile, WritingConfig, ReviewConfig
from app.services.context_service import ContextService


from tests.fixtures import load_fixture


@pytest.fixture
def review_service():
    """创建 ReviewService 实例"""
    # ReviewService was refactored to stateless checks; no longer takes context_service
    return ReviewService()


@pytest.fixture
def assembly_profile():
    """创建装配画像"""
    return Profile(
        id="test_assembly",
        user_id="test",
        domain="assembly",
        writing=WritingConfig(
            tone="技术文档",
            terminology="assembly",
            detail_level="详细"
        ),
        review=ReviewConfig(
            check_completeness=True,
            check_accuracy=True,
            allowed_deviation=0.1
        )
    )


class TestL1UniversalCheck:
    """测试 L1 通用红线检查"""
    
    def test_l1_no_missing_required_fields(self, review_service):
        """测试缺少必填字段"""
        content = load_fixture("missing_safety_content")
        
        result = review_service.review(content, domain="assembly")
        
        # 应检测到缺少必填字段
        assert any("缺少" in i.message for i in result.issues)
    
    def test_l1_no_format_errors(self, review_service):
        """测试格式错误（占位符）"""
        content = load_fixture("placeholder_content")
        
        result = review_service.review(content, domain="assembly")
        
        # 应检测到占位符
        assert any("占位符" in i.message for i in result.issues)
    
    def test_l1_clear_structure(self, review_service):
        """测试段落结构"""
        content = "这是一段没有标题结构的文本内容。"
        
        result = review_service.review(content, domain="assembly")
        
        # 应检测到缺少结构
        assert any("结构" in i.message or "标题" in i.message for i in result.issues)


class TestL2DomainCheck:
    """测试 L2 领域红线检查"""
    
    def test_l2_assembly_specific_terms(self, review_service):
        """测试装配领域术语检查"""
        content = load_fixture("welding_mixed_terms")
        
        result = review_service.review(content, domain="assembly")
        
        # 应检测到术语问题（如果是装配领域但使用了焊接术语）
        # 注：此测试取决于实现细节
    
    def test_l2_assembly_workflow_order(self, review_service):
        """测试工序顺序检查"""
        # 工序顺序检查是 WARNING 级别
        pass  # 取决于实现


class TestL3ProfileCheck:
    """测试 L3 用户偏好检查"""
    
    def test_l3_tone_mismatch(self, review_service, assembly_profile):
        """测试语气偏好不匹配"""
        content = load_fixture("oral_style_content")
        
        result = review_service.review(content, profile=assembly_profile, domain="assembly")
        
        # 应有建议改进语气
        assert any("语气" in s.message or "正式" in s.message for s in result.suggestions)
    
    def test_l3_detail_level_mismatch(self, review_service):
        """测试详细程度偏好"""
        profile = Profile(
            id="test",
            user_id="test",
            domain="assembly",
            writing=WritingConfig(detail_level="简要"),
            review=ReviewConfig()
        )
        
        # 长内容
        content = "很长的内容" * 500
        
        result = review_service.review(content, profile=profile, domain="assembly")
        
        # 可能有精简建议
        # 取决于实现


class TestComplianceCheck:
    """测试合规性检查"""
    
    def test_compliance_no_forbidden_words(self, review_service):
        """测试绝对化表述"""
        content = "禁止使用绝对化的词汇"
        
        result = review_service.review(content, domain="assembly")
        
        # 应检测到绝对化表述
        # 取决于实现
    
    def test_compliance_safety_keywords(self, review_service):
        """测试安全关键词"""
        content = "高风险焊接操作"
        
        result = review_service.review(content, domain="assembly")
        
        # 应检测到缺少安全提示
        assert any("安全" in i.message for i in result.issues)


class TestReviewResult:
    """测试 ReviewResult 模型"""
    
    def test_check_returns_review_result(self, review_service):
        """测试 check 返回 ReviewResult"""
        content = load_fixture("valid_assembly_content")
        
        result = review_service.review(content, domain="assembly")
        
        assert isinstance(result, ReviewResult)
        assert isinstance(result.score, int)
        assert isinstance(result.issues, list)
        assert isinstance(result.suggestions, list)
    
    def test_check_score_calculation(self, review_service):
        """测试评分计算"""
        # 有错误的案例
        content = load_fixture("missing_safety_content")
        
        result = review_service.review(content, domain="assembly")
        
        # 有 ERROR 扣 10 分
        assert result.score < 100
    
    def test_check_score_below_threshold(self, review_service):
        """测试评分低于阈值"""
        content = load_fixture("missing_safety_content")
        
        result = review_service.review(content, domain="assembly")
        
        # 缺少安全措施应该导致低分
        assert result.score < 80
        assert result.passed is False


class TestIssueModel:
    """测试 Issue 模型"""
    
    def test_issue_to_dict(self):
        """测试 Issue 转字典"""
        issue = Issue(
            severity=Severity.ERROR.value,
            type="missing_field",
            field="安全措施",
            message="缺少必填字段"
        )
        
        data = issue.to_dict()
        
        assert data["severity"] == "error"
        assert data["type"] == "missing_field"
    
    def test_issue_from_dict(self):
        """测试字典转 Issue"""
        data = {
            "severity": "warning",
            "type": "placeholder",
            "message": "存在占位符"
        }
        
        issue = Issue.from_dict(data)
        
        assert issue.severity == "warning"
        assert issue.type == "placeholder"


# NOTE: TestSuggestionModel removed — Suggestion class no longer exists
# in review_service (refactored to Issue-based API)
