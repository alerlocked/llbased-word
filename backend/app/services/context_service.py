"""
ContextService - 上下文管理服务

管理模板、画像、示例的统一服务
"""
from typing import List, Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass, field
import yaml
import logging

from app.models.profile import Profile, WritingConfig, ReviewConfig


logger = logging.getLogger(__name__)


@dataclass
class Template:
    """
    文档模板
    
    定义文档的结构、必填字段和样式指南
    """
    id: str
    domain: str  # assembly, welding, coating, etc.
    doc_type: str  # work_instruction, procedure, standard, etc.
    structure: List[str] = field(default_factory=list)
    required_fields: List[str] = field(default_factory=list)
    style_guide: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "domain": self.domain,
            "doc_type": self.doc_type,
            "structure": self.structure,
            "required_fields": self.required_fields,
            "style_guide": self.style_guide
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Template":
        return cls(
            id=data.get("id", ""),
            domain=data.get("domain", ""),
            doc_type=data.get("doc_type", ""),
            structure=data.get("structure", []),
            required_fields=data.get("required_fields", []),
            style_guide=data.get("style_guide", {})
        )
    
    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "Template":
        """从 YAML 文件加载模板"""
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)


@dataclass
class Example:
    """
    示例文档
    
    用于给 Agent 提供参考
    """
    id: str
    domain: str
    title: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextService:
    """
    上下文管理服务
    
    职责：
    - 加载用户画像
    - 加载文档模板
    - 加载示例文档
    - 构建完整上下文
    """
    
    # 默认资源路径
    DEFAULT_PROFILES_DIR = Path(".project-meta/profiles")
    DEFAULT_TEMPLATES_DIR = Path(".project-meta/templates")
    DEFAULT_RULES_DIR = Path(".project-meta/rules")
    
    def __init__(
        self,
        base_path: Optional[Path] = None,
        profiles_dir: Optional[Path] = None,
        templates_dir: Optional[Path] = None,
        rules_dir: Optional[Path] = None
    ):
        """
        初始化上下文服务
        
        Args:
            base_path: 基础路径（项目根目录）
            profiles_dir: 画像目录
            templates_dir: 模板目录
            rules_dir: 规则目录
        """
        self.base_path = base_path or Path.cwd()
        self.profiles_dir = profiles_dir or self.base_path / self.DEFAULT_PROFILES_DIR
        self.templates_dir = templates_dir or self.base_path / self.DEFAULT_TEMPLATES_DIR
        self.rules_dir = rules_dir or self.base_path / self.DEFAULT_RULES_DIR
        
        # 缓存
        self._profile_cache: Dict[str, Profile] = {}
        self._template_cache: Dict[str, Template] = {}
        
        logger.info(
            "context_service_initialized",
            profiles_dir=str(self.profiles_dir),
            templates_dir=str(self.templates_dir),
            rules_dir=str(self.rules_dir)
        )
    
    # ========================================
    # Profile API
    # ========================================
    
    def load_profile(self, user_id: str, domain: str) -> Profile:
        """
        加载用户画像

        Lookup order:
        1. JSON profile (from profile API: data/profiles/{user_id}.json)
        2. YAML profile (legacy: .project-meta/profiles/{user_id}_{domain}.yaml)
        3. Default profile

        Args:
            user_id: 用户ID
            domain: 领域

        Returns:
            Profile 对象
        """
        import json
        from app.config import settings

        cache_key = f"{user_id}_{domain}"
        if cache_key in self._profile_cache:
            return self._profile_cache[cache_key]

        # 1. Try JSON profile from profile API storage
        json_path = Path(settings.DATA_DIR) / "profiles" / f"{user_id}.json"
        if json_path.exists():
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                profile = Profile.from_dict(data)
                self._profile_cache[cache_key] = profile
                logger.info("loaded_json_profile", user_id=user_id, domain=domain)
                return profile
            except Exception as e:
                logger.error("failed_to_load_json_profile", error=str(e))

        # 2. Try legacy YAML profile
        yaml_path = self.profiles_dir / f"{user_id}_{domain}.yaml"
        if yaml_path.exists():
            try:
                profile = Profile.from_yaml(yaml_path)
                self._profile_cache[cache_key] = profile
                logger.info("loaded_yaml_profile", user_id=user_id, domain=domain)
                return profile
            except Exception as e:
                logger.error("failed_to_load_yaml_profile", error=str(e))

        # 3. Default profile
        default_profile = self._load_default_profile(domain)
        self._profile_cache[cache_key] = default_profile
        logger.info("loaded_default_profile", user_id=user_id, domain=domain)
        return default_profile
    
    def _load_default_profile(self, domain: str) -> Profile:
        """
        加载领域默认画像
        
        Args:
            domain: 领域
            
        Returns:
            Profile 对象
        """
        default_path = self.profiles_dir / f"default_{domain}.yaml"
        
        if default_path.exists():
            try:
                return Profile.from_yaml(default_path)
            except Exception as e:
                logger.error("failed_to_load_default_profile", error=str(e), domain=domain)
        
        # 如果没有默认画像文件，创建内置默认
        logger.warning("no_default_profile_found, using builtin", domain=domain)
        from app.models.profile import get_default_assembly_profile, get_default_welding_profile
        
        if domain == "assembly":
            return get_default_assembly_profile()
        elif domain == "welding":
            return get_default_welding_profile()
        else:
            # 通用默认
            return Profile(
                id=f"default_{domain}",
                user_id="default",
                domain=domain,
                writing=WritingConfig(),
                review=ReviewConfig()
            )
    
    # ========================================
    # Template API
    # ========================================
    
    def load_template(self, domain: str, doc_type: str) -> Template:
        """
        加载文档模板
        
        Args:
            domain: 领域
            doc_type: 文档类型（work_instruction, procedure, etc.）
            
        Returns:
            Template 对象
        """
        cache_key = f"{domain}_{doc_type}"
        if cache_key in self._template_cache:
            return self._template_cache[cache_key]
        
        # 尝试加载模板文件
        template_name = f"{domain}_{doc_type}.yaml"
        template_path = self.templates_dir / template_name
        
        if template_path.exists():
            try:
                template = Template.from_yaml(template_path)
                self._template_cache[cache_key] = template
                logger.info("loaded_template", domain=domain, doc_type=doc_type)
                return template
            except Exception as e:
                logger.error("failed_to_load_template", error=str(e), path=str(template_path))
        
        # 返回空模板
        logger.warning("template_not_found, using empty", domain=domain, doc_type=doc_type)
        return Template(
            id=f"{domain}_{doc_type}",
            domain=domain,
            doc_type=doc_type
        )
    
    # ========================================
    # Examples API
    # ========================================
    
    def load_examples(self, domain: str, limit: int = 3) -> List[Example]:
        """
        加载示例文档
        
        Args:
            domain: 领域
            limit: 最大数量
            
        Returns:
            Example 列表
        """
        # TODO: 实现从知识库或文件系统加载示例
        # 目前返回空列表
        logger.info("load_examples_called", domain=domain, limit=limit)
        return []
    
    # ========================================
    # Context Building API
    # ========================================
    
    def build_context(
        self,
        user_id: str,
        domain: str,
        doc_type: str
    ) -> str:
        """
        构建完整上下文
        
        Args:
            user_id: 用户ID
            domain: 领域
            doc_type: 文档类型
            
        Returns:
            上下文字符串
        """
        parts = []
        
        # 1. 加载模板
        template = self.load_template(domain, doc_type)
        template_context = self._build_template_context(template)
        parts.append("【模板】\n" + template_context)
        
        # 2. 加载画像
        profile = self.load_profile(user_id, domain)
        profile_context = self._build_profile_context(profile)
        parts.append("【画像】\n" + profile_context)
        
        # 3. 加载示例
        examples = self.load_examples(domain, limit=3)
        if examples:
            examples_context = self._build_examples_context(examples)
            parts.append("【示例】\n" + examples_context)
        
        context = "\n\n".join(parts)
        
        logger.info(
            "context_built",
            user_id=user_id,
            domain=domain,
            doc_type=doc_type,
            context_length=len(context)
        )
        
        return context
    
    def _build_template_context(self, template: Template) -> str:
        """构建模板上下文"""
        parts = []
        
        parts.append(f"文档结构：{' -> '.join(template.structure)}")
        
        if template.required_fields:
            parts.append(f"\n必填字段：")
            for field in template.required_fields:
                parts.append(f"  - {field}")
        
        if template.style_guide:
            parts.append("\n样式指南：")
            for key, value in template.style_guide.items():
                parts.append(f"  - {key}: {value}")
        
        return "\n".join(parts)
    
    def _build_profile_context(self, profile: Profile) -> str:
        """构建画像上下文"""
        parts = []
        
        parts.append(f"写作风格：{profile.writing.tone}")
        parts.append(f"术语库：{profile.writing.terminology}")
        parts.append(f"详细程度：{profile.writing.detail_level}")
        parts.append(f"\n审查标准：")
        parts.append(f"  - 完整性检查：{profile.review.check_completeness}")
        parts.append(f"  - 准确性检查：{profile.review.check_accuracy}")
        parts.append(f"  - 允许偏差：{profile.review.allowed_deviation * 100}%")
        
        return "\n".join(parts)
    
    def _build_examples_context(self, examples: List[Example]) -> str:
        """构建示例上下文"""
        parts = []
        
        for i, example in enumerate(examples, 1):
            parts.append(f"示例 {i}: {example.title}")
            parts.append(example.content[:500] + "...")
            parts.append("")
        
        return "\n".join(parts)
    
    # ========================================
    # Update Profile API（预留）
    # ========================================
    
    def update_profile_from_feedback(
        self,
        user_id: str,
        domain: str,
        feedback: Dict[str, Any]
    ) -> bool:
        """
        从反馈更新用户画像（预留接口）
        
        Args:
            user_id: 用户ID
            domain: 领域
            feedback: 反馈数据
            
        Returns:
            是否更新成功
        """
        logger.info(
            "update_profile_from_feedback_called",
            user_id=user_id,
            domain=domain,
            feedback_keys=list(feedback.keys())
        )
        
        # TODO: 实现画像学习逻辑
        # 1. 加载当前画像
        # 2. 分析反馈，提取偏好
        # 3. 更新画像
        # 4. 保存画像
        
        # 目前只记录日志
        return True
    
    # ========================================
    # Rules API
    # ========================================
    
    def load_rules(self, level: str, domain: Optional[str] = None) -> Dict[str, Any]:
        """
        加载审查规则
        
        Args:
            level: 规则级别（l1, l2, l3）
            domain: 领域（L2 需要）
            
        Returns:
            规则字典
        """
        if level == "l1":
            rule_file = self.rules_dir / "l1_universal.yaml"
        elif level == "l2" and domain:
            rule_file = self.rules_dir / f"l2_{domain}.yaml"
        elif level == "l3":
            # L3 从画像中提取
            return {"type": "profile_based"}
        else:
            return {}
        
        if rule_file.exists():
            try:
                with open(rule_file, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                logger.error("failed_to_load_rules", error=str(e), path=str(rule_file))
                return {}
        
        return {}
