"""
Profile 模型

用户画像模型，包含写作配置和审查配置
"""
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
import yaml
import uuid


@dataclass
class WritingConfig:
    """
    写作配置
    
    定义内容生成的风格偏好
    """
    tone: str = "技术文档"           # 语气：技术文档/培训材料/操作手册
    terminology: str = "standard"    # 术语库：standard/assembly/welding/coating
    detail_level: str = "详细"        # 详细程度：简要/适中/详细
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WritingConfig":
        return cls(
            tone=data.get("tone", "技术文档"),
            terminology=data.get("terminology", "standard"),
            detail_level=data.get("detail_level", "详细")
        )


@dataclass
class ReviewConfig:
    """
    审查配置
    
    定义内容审查的标准和严格程度
    """
    check_completeness: bool = True      # 是否检查完整性
    check_accuracy: bool = True          # 是否检查准确性
    allowed_deviation: float = 0.1       # 允许的模板偏差（0.0-1.0）
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewConfig":
        return cls(
            check_completeness=data.get("check_completeness", True),
            check_accuracy=data.get("check_accuracy", True),
            allowed_deviation=data.get("allowed_deviation", 0.1)
        )


@dataclass
class Profile:
    """
    用户画像
    
    包含用户的写作偏好和审查标准
    """
    id: str
    user_id: str
    domain: str  # assembly, welding, coating, etc.
    writing: WritingConfig = field(default_factory=WritingConfig)
    review: ReviewConfig = field(default_factory=ReviewConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "domain": self.domain,
            "writing": self.writing.to_dict(),
            "review": self.review.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Profile":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            user_id=data.get("user_id", "default"),
            domain=data.get("domain", "assembly"),
            writing=WritingConfig.from_dict(data.get("writing", {})),
            review=ReviewConfig.from_dict(data.get("review", {}))
        )
    
    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "Profile":
        """
        从 YAML 文件加载画像
        
        Args:
            yaml_path: YAML 文件路径
            
        Returns:
            Profile 对象
        """
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    def to_yaml(self, yaml_path: Path):
        """
        保存画像到 YAML 文件
        
        Args:
            yaml_path: YAML 文件路径
        """
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.to_dict(), f, allow_unicode=True, default_flow_style=False)


# ========================================
# 预定义的默认画像
# ========================================

def get_default_assembly_profile() -> Profile:
    """获取默认装配画像"""
    return Profile(
        id="default_assembly",
        user_id="default",
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


def get_default_welding_profile() -> Profile:
    """获取默认焊接画像"""
    return Profile(
        id="default_welding",
        user_id="default",
        domain="welding",
        writing=WritingConfig(
            tone="技术文档",
            terminology="welding",
            detail_level="详细"
        ),
        review=ReviewConfig(
            check_completeness=True,
            check_accuracy=True,
            allowed_deviation=0.1
        )
    )
