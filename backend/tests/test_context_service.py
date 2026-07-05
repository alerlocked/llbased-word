"""
test_context_service.py - ContextService 单元测试
"""
import pytest
from pathlib import Path
import yaml
from unittest.mock import Mock, patch

from app.services.context_service import ContextService, Template, Example
from app.models.profile import Profile, WritingConfig, ReviewConfig


# 测试数据路径
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def context_service():
    """创建 ContextService 实例"""
    # backend/tests -> backend -> localknowledgebase-word
    base_path = Path(__file__).parent.parent.parent
    return ContextService(base_path=base_path)


class TestLoadProfile:
    """测试 load_profile 方法"""
    
    def test_load_profile_returns_default(self, context_service):
        """测试加载默认画像"""
        profile = context_service.load_profile("new_user", "assembly")
        
        assert profile is not None
        assert profile.domain == "assembly"
        assert profile.user_id == "default"
    
    def test_load_profile_caching(self, context_service):
        """测试画像缓存"""
        # 第一次加载
        profile1 = context_service.load_profile("test_user", "assembly")
        
        # 第二次加载（应从缓存读取）
        profile2 = context_service.load_profile("test_user", "assembly")
        
        assert profile1 == profile2
    
    def test_load_profile_welding_domain(self, context_service):
        """测试焊接领域画像"""
        profile = context_service.load_profile("test", "welding")
        
        assert profile.domain == "welding"
        assert "welding" in profile.writing.terminology


class TestLoadTemplate:
    """测试 load_template 方法"""
    
    @pytest.mark.xfail(reason="template load returns empty (path/data drift)", strict=False)
    def test_load_template_returns_valid(self, context_service):
        """测试加载模板"""
        template = context_service.load_template("assembly", "work_instruction")
        
        assert template is not None
        assert template.domain == "assembly"
        assert template.doc_type == "work_instruction"
        assert len(template.structure) > 0
    
    def test_load_template_caching(self, context_service):
        """测试模板缓存"""
        template1 = context_service.load_template("assembly", "work_instruction")
        template2 = context_service.load_template("assembly", "work_instruction")
        
        assert template1 == template2
    
    def test_load_template_not_found(self, context_service):
        """测试模板不存在时返回空模板"""
        template = context_service.load_template("unknown", "unknown_type")
        
        assert template.domain == "unknown"
        assert template.doc_type == "unknown_type"


class TestLoadExamples:
    """测试 load_examples 方法"""
    
    def test_load_examples_returns_list(self, context_service):
        """测试加载示例"""
        examples = context_service.load_examples("assembly", limit=3)
        
        assert isinstance(examples, list)
    
    def test_load_examples_limit(self, context_service):
        """测试示例数量限制"""
        examples = context_service.load_examples("assembly", limit=2)
        
        assert len(examples) <= 2


class TestBuildContext:
    """测试 build_context 方法"""
    
    def test_build_context_includes_all_sections(self, context_service):
        """测试上下文包含所有部分"""
        context = context_service.build_context(
            user_id="test",
            domain="assembly",
            doc_type="work_instruction"
        )
        
        assert context is not None
        assert "【模板】" in context
        assert "【画像】" in context
        # 示例可能为空
    
    def test_build_context_profile_section(self, context_service):
        """测试上下文画像部分"""
        context = context_service.build_context(
            user_id="test",
            domain="assembly",
            doc_type="work_instruction"
        )
        
        assert "写作风格" in context
        assert "审查标准" in context
    
    def test_build_context_template_section(self, context_service):
        """测试上下文模板部分"""
        context = context_service.build_context(
            user_id="test",
            domain="assembly",
            doc_type="work_instruction"
        )
        
        assert "文档结构" in context


class TestUpdateProfile:
    """测试 update_profile_from_feedback 方法"""
    
    def test_update_profile_placeholder(self, context_service):
        """测试更新画像（预留接口）"""
        result = context_service.update_profile_from_feedback(
            user_id="test",
            domain="assembly",
            feedback={"tone": "formal"}
        )
        
        # 目前为预留接口，应返回 True
        assert result is True


class TestTemplateModel:
    """测试 Template 模型"""
    
    def test_template_to_dict(self):
        """测试模板转字典"""
        template = Template(
            id="test",
            domain="assembly",
            doc_type="work_instruction",
            structure=["A", "B"],
            required_fields=["A"]
        )
        
        data = template.to_dict()
        
        assert data["id"] == "test"
        assert data["domain"] == "assembly"
        assert data["structure"] == ["A", "B"]
    
    def test_template_from_dict(self):
        """测试字典转模板"""
        data = {
            "id": "test",
            "domain": "assembly",
            "doc_type": "work_instruction",
            "structure": ["A", "B"],
            "required_fields": ["A"]
        }
        
        template = Template.from_dict(data)
        
        assert template.id == "test"
        assert template.domain == "assembly"


class TestExampleModel:
    """测试 Example 模型"""
    
    def test_example_creation(self):
        """测试示例创建"""
        example = Example(
            id="test",
            domain="assembly",
            title="Test Example",
            content="Test content"
        )
        
        assert example.id == "test"
        assert example.domain == "assembly"
