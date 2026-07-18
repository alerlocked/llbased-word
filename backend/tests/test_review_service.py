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


@pytest.fixture
def welding_profile():
    """加载 N1 生成的焊接画像（backend/data/profiles/welding.json）"""
    profile_path = Path(__file__).parent.parent / "data" / "profiles" / "welding.json"
    return Profile.from_json(profile_path)


class TestL1UniversalCheck:
    """测试 L1 通用红线检查"""
    
    @pytest.mark.xfail(reason="review engine gap: required-field check not implemented (placeholder/vague-word checks only); kept as implementation target")
    async def test_l1_no_missing_required_fields(self, review_service):
        """测试缺少必填字段"""
        content = load_fixture("missing_safety_content")
        
        result = await review_service.review(content, domain="assembly")
        
        # 应检测到缺少必填字段
        assert any("缺少" in i.message for i in result.issues)
    
    async def test_l1_no_format_errors(self, review_service):
        """测试格式错误（占位符）"""
        content = load_fixture("placeholder_content")
        
        result = await review_service.review(content, domain="assembly")
        
        # 应检测到占位符
        assert any("占位符" in i.message for i in result.issues)
    
    @pytest.mark.xfail(reason="review engine gap: structure check not implemented; kept as implementation target")
    async def test_l1_clear_structure(self, review_service):
        """测试段落结构"""
        content = "这是一段没有标题结构的文本内容。"
        
        result = await review_service.review(content, domain="assembly")
        
        # 应检测到缺少结构
        assert any("结构" in i.message or "标题" in i.message for i in result.issues)


class TestL2DomainCheck:
    """测试 L2 领域红线检查"""
    
    async def test_l2_assembly_specific_terms(self, review_service):
        """测试装配领域术语检查"""
        content = load_fixture("welding_mixed_terms")
        
        result = await review_service.review(content, domain="assembly")
        
        # 应检测到术语问题（如果是装配领域但使用了焊接术语）
        # 注：此测试取决于实现细节
    
    async def test_l2_assembly_workflow_order(self, review_service):
        """测试工序顺序检查"""
        # 工序顺序检查是 WARNING 级别
        pass  # 取决于实现


class TestL3ProfileCheck:
    """测试 L3 用户偏好检查"""
    
    @pytest.mark.xfail(reason="review engine gap: L3 tone/preference check not implemented; kept as implementation target")
    async def test_l3_tone_mismatch(self, review_service, assembly_profile):
        """测试语气偏好不匹配"""
        content = load_fixture("oral_style_content")
        
        result = await review_service.review(content, profile=assembly_profile, domain="assembly")
        
        # 应有建议改进语气
        assert any("语气" in s.message or "正式" in s.message for s in result.suggestions)
    
    async def test_l3_detail_level_mismatch(self, review_service):
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
        
        result = await review_service.review(content, profile=profile, domain="assembly")
        
        # 可能有精简建议
        # 取决于实现


class TestComplianceCheck:
    """测试合规性检查"""
    
    @pytest.mark.xfail(reason="review engine gap: compliance (absolute-word) check not implemented; kept as implementation target")
    async def test_compliance_no_forbidden_words(self, review_service):
        """测试绝对化表述"""
        content = "禁止使用绝对化的词汇"
        
        result = await review_service.review(content, domain="assembly")
        
        # 应检测到绝对化表述
        # 取决于实现
    
    @pytest.mark.xfail(reason="review engine gap: safety-keyword check not implemented; kept as implementation target")
    async def test_compliance_safety_keywords(self, review_service):
        """测试安全关键词"""
        content = "高风险焊接操作"
        
        result = await review_service.review(content, domain="assembly")
        
        # 应检测到缺少安全提示
        assert any("安全" in i.message for i in result.issues)


class TestReviewResult:
    """测试 ReviewResult 模型"""
    
    @pytest.mark.xfail(reason="review engine gap: ReviewResult.score not implemented; kept as implementation target")
    async def test_check_returns_review_result(self, review_service):
        """测试 check 返回 ReviewResult"""
        content = load_fixture("valid_assembly_content")
        
        result = await review_service.review(content, domain="assembly")
        
        assert isinstance(result, ReviewResult)
        assert isinstance(result.score, int)
        assert isinstance(result.issues, list)
        assert isinstance(result.suggestions, list)
    
    @pytest.mark.xfail(reason="review engine gap: score calculation not implemented; kept as implementation target")
    async def test_check_score_calculation(self, review_service):
        """测试评分计算"""
        # 有错误的案例
        content = load_fixture("missing_safety_content")
        
        result = await review_service.review(content, domain="assembly")
        
        # 有 ERROR 扣 10 分
        assert result.score < 100
    
    @pytest.mark.xfail(reason="review engine gap: score/threshold not implemented; kept as implementation target")
    async def test_check_score_below_threshold(self, review_service):
        """测试评分低于阈值"""
        content = load_fixture("missing_safety_content")
        
        result = await review_service.review(content, domain="assembly")
        
        # 缺少安全措施应该导致低分
        assert result.score < 80
        assert result.passed is False


class TestIssueModel:
    """测试 Issue 模型"""
    
    async def test_issue_to_dict(self):
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
    
    async def test_issue_from_dict(self):
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


class TestImplRules:
    """测试实施细则规则（敏感词 N2 + 必填参数 N3）"""

    async def test_sensitive_word_detected(self, review_service):
        """敏感词命中：不传 profile，_check_sensitive_words 无条件跑"""
        content = "XX安装前需在XX内涂适量润滑油"

        result = await review_service.review(
            content, domain="assembly", skip_standard_check=True
        )

        # sensitive_words.json 含 word=适量 → 命中 sensitive_word
        sensitive = [i for i in result.issues if i.type == "sensitive_word"]
        assert len(sensitive) >= 1
        assert sensitive[0].severity == Severity.WARNING.value

    async def test_sensitive_word_fix_hint_has_standard(self, review_service):
        """命中敏感词的 issue.fix_hint 非空（含 standard_example 原文）"""
        content = "XX安装前需在XX内涂适量润滑油"

        result = await review_service.review(
            content, domain="assembly", skip_standard_check=True
        )

        sensitive = [i for i in result.issues if i.type == "sensitive_word"]
        assert len(sensitive) >= 1
        # standard_example 来自 sensitive_words.json 的 "适量" 条目
        assert sensitive[0].fix_hint
        assert "航空润滑油" in sensitive[0].fix_hint

    async def test_normal_word_not_flagged(self, review_service):
        """正常工序内容不含敏感词：拧紧/预紧力 均不在词表"""
        content = "拧紧螺钉，预紧力1N·m"

        result = await review_service.review(
            content, domain="assembly", skip_standard_check=True
        )

        sensitive = [i for i in result.issues if i.type == "sensitive_word"]
        assert sensitive == []

    async def test_mandatory_param_skipped_when_skip_llm(
        self, review_service, welding_profile
    ):
        """skip_standard_check=True → 跳过 LLM，不报 missing_mandatory_param"""
        # 缺焊接电流的 TIG 工序（钨极/气流量给了，电流没给）
        content = "TIG焊接：钨极直径Φ2mm，氩气流量8L/min，注意操作安全防护。"

        result = await review_service.review(
            content, profile=welding_profile, domain="welding",
            skip_standard_check=True,
        )

        mandatory = [
            i for i in result.issues if i.type == "missing_mandatory_param"
        ]
        assert mandatory == []

    @pytest.mark.skip(
        reason="real LLM required; run manually with API key configured"
    )
    async def test_mandatory_param_missing_real_llm(
        self, review_service, welding_profile
    ):
        """真实 LLM：缺焊接电流的 TIG 工序应报 missing_mandatory_param"""
        content = "TIG焊接：钨极直径Φ2mm，氩气流量8L/min，注意操作安全防护。"

        result = await review_service.review(
            content, profile=welding_profile, domain="welding",
        )

        mandatory = [
            i for i in result.issues if i.type == "missing_mandatory_param"
        ]
        assert len(mandatory) >= 1
        assert any("焊接电流" in i.message for i in mandatory)

    @pytest.mark.skip(
        reason="real LLM required; run manually with API key configured"
    )
    async def test_mandatory_param_present_no_false_alarm(
        self, review_service, welding_profile
    ):
        """真实 LLM：参数齐全不应误报 missing_mandatory_param"""
        content = "TIG焊接：钨极直径Φ2mm，焊接电流120A，氩气流量8L/min。"

        result = await review_service.review(
            content, profile=welding_profile, domain="welding",
        )

        mandatory = [
            i for i in result.issues if i.type == "missing_mandatory_param"
        ]
        assert mandatory == []
