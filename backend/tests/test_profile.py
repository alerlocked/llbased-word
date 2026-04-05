"""
test_profile.py - Profile 模型单元测试
"""
import pytest
from pathlib import Path
import yaml

from app.models.profile import (
    Profile,
    WritingConfig,
    ReviewConfig,
    get_default_assembly_profile,
    get_default_welding_profile
)


class TestWritingConfig:
    """测试 WritingConfig 模型"""
    
    def test_writing_config_defaults(self):
        """测试 WritingConfig 默认值"""
        config = WritingConfig()
        
        assert config.tone == "技术文档"
        assert config.terminology == "standard"
        assert config.detail_level == "详细"
    
    def test_writing_config_to_dict(self):
        """测试 WritingConfig 转字典"""
        config = WritingConfig(
            tone="培训材料",
            terminology="assembly",
            detail_level="简要"
        )
        
        data = config.to_dict()
        
        assert data["tone"] == "培训材料"
        assert data["terminology"] == "assembly"
        assert data["detail_level"] == "简要"
    
    def test_writing_config_from_dict(self):
        """测试字典转 WritingConfig"""
        data = {
            "tone": "操作手册",
            "terminology": "welding",
            "detail_level": "适中"
        }
        
        config = WritingConfig.from_dict(data)
        
        assert config.tone == "操作手册"
        assert config.terminology == "welding"
        assert config.detail_level == "适中"


class TestReviewConfig:
    """测试 ReviewConfig 模型"""
    
    def test_review_config_defaults(self):
        """测试 ReviewConfig 默认值"""
        config = ReviewConfig()
        
        assert config.check_completeness is True
        assert config.check_accuracy is True
        assert config.allowed_deviation == 0.1
    
    def test_review_config_to_dict(self):
        """测试 ReviewConfig 转字典"""
        config = ReviewConfig(
            check_completeness=False,
            check_accuracy=True,
            allowed_deviation=0.2
        )
        
        data = config.to_dict()
        
        assert data["check_completeness"] is False
        assert data["check_accuracy"] is True
        assert data["allowed_deviation"] == 0.2
    
    def test_review_config_from_dict(self):
        """测试字典转 ReviewConfig"""
        data = {
            "check_completeness": False,
            "check_accuracy": False,
            "allowed_deviation": 0.15
        }
        
        config = ReviewConfig.from_dict(data)
        
        assert config.check_completeness is False
        assert config.check_accuracy is False
        assert config.allowed_deviation == 0.15


class TestProfile:
    """测试 Profile 模型"""
    
    def test_profile_required_fields(self):
        """测试 Profile 必需字段"""
        profile = Profile(
            id="test_id",
            user_id="test_user",
            domain="assembly"
        )
        
        assert profile.id == "test_id"
        assert profile.user_id == "test_user"
        assert profile.domain == "assembly"
    
    def test_profile_with_configs(self):
        """测试带配置的 Profile"""
        profile = Profile(
            id="test",
            user_id="user",
            domain="welding",
            writing=WritingConfig(tone="操作手册"),
            review=ReviewConfig(allowed_deviation=0.2)
        )
        
        assert profile.writing.tone == "操作手册"
        assert profile.review.allowed_deviation == 0.2
    
    def test_profile_to_dict(self):
        """测试 Profile 转字典"""
        profile = Profile(
            id="test",
            user_id="user",
            domain="assembly",
            writing=WritingConfig(tone="技术文档"),
            review=ReviewConfig(check_completeness=True)
        )
        
        data = profile.to_dict()
        
        assert data["id"] == "test"
        assert data["user_id"] == "user"
        assert data["domain"] == "assembly"
        assert "writing" in data
        assert "review" in data
    
    def test_profile_from_dict(self):
        """测试字典转 Profile"""
        data = {
            "id": "test",
            "user_id": "user",
            "domain": "welding",
            "writing": {
                "tone": "操作手册",
                "terminology": "welding",
                "detail_level": "详细"
            },
            "review": {
                "check_completeness": True,
                "check_accuracy": True,
                "allowed_deviation": 0.1
            }
        }
        
        profile = Profile.from_dict(data)
        
        assert profile.id == "test"
        assert profile.writing.tone == "操作手册"
        assert profile.review.allowed_deviation == 0.1


class TestProfileFromYAML:
    """测试从 YAML 文件加载 Profile"""
    
    @pytest.fixture
    def profiles_dir(self):
        """获取 profiles 目录"""
        return Path(__file__).parent.parent.parent.parent / ".project-meta" / "profiles"
    
    def test_profile_from_yaml_assembly(self, profiles_dir):
        """测试从 YAML 加载装配画像"""
        yaml_path = profiles_dir / "default_assembly.yaml"
        
        if yaml_path.exists():
            profile = Profile.from_yaml(yaml_path)
            
            assert profile.domain == "assembly"
            assert profile.writing.terminology == "assembly"
    
    def test_profile_from_yaml_welding(self, profiles_dir):
        """测试从 YAML 加载焊接画像"""
        yaml_path = profiles_dir / "default_welding.yaml"
        
        if yaml_path.exists():
            profile = Profile.from_yaml(yaml_path)
            
            assert profile.domain == "welding"
            assert profile.writing.terminology == "welding"
    
    def test_profile_to_yaml(self, tmp_path):
        """测试保存 Profile 到 YAML"""
        profile = Profile(
            id="test_save",
            user_id="test_user",
            domain="test_domain",
            writing=WritingConfig(tone="测试语气"),
            review=ReviewConfig(allowed_deviation=0.05)
        )
        
        yaml_path = tmp_path / "test_profile.yaml"
        profile.to_yaml(yaml_path)
        
        # 重新加载
        loaded = Profile.from_yaml(yaml_path)
        
        assert loaded.id == "test_save"
        assert loaded.writing.tone == "测试语气"
        assert loaded.review.allowed_deviation == 0.05


class TestDefaultProfiles:
    """测试预定义的默认画像"""
    
    def test_get_default_assembly_profile(self):
        """测试获取默认装配画像"""
        profile = get_default_assembly_profile()
        
        assert profile.id == "default_assembly"
        assert profile.domain == "assembly"
        assert profile.writing.terminology == "assembly"
    
    def test_get_default_welding_profile(self):
        """测试获取默认焊接画像"""
        profile = get_default_welding_profile()
        
        assert profile.id == "default_welding"
        assert profile.domain == "welding"
        assert profile.writing.terminology == "welding"
