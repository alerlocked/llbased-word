"""
Profile 模型

用户画像模型，包含写作配置、审查配置和动态偏好
"""
from typing import Optional, Dict, Any, List
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
class WritingPreferences:
    """
    Dynamic writing preferences learned from user interactions.

    Extends WritingConfig with structured preference data that evolves
    as the user edits AI-generated content.
    """
    # Base config (inherited fields)
    tone: str = "技术文档"
    terminology: str = "standard"
    detail_level: str = "详细"

    # Learned preferences
    preferred_sentence_length: str = "medium"  # short/medium/long
    use_passive_voice: bool = True
    include_examples: bool = True
    include_caution_notes: bool = True
    section_order_preference: List[str] = field(default_factory=list)
    custom_vocabulary: Dict[str, str] = field(default_factory=dict)
    avoid_phrases: List[str] = field(default_factory=list)

    # Metadata
    confidence: float = 0.0  # 0.0-1.0, how confident we are in these prefs
    sample_count: int = 0    # Number of interactions used to learn
    last_updated: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WritingPreferences":
        return cls(
            tone=data.get("tone", "技术文档"),
            terminology=data.get("terminology", "standard"),
            detail_level=data.get("detail_level", "详细"),
            preferred_sentence_length=data.get("preferred_sentence_length", "medium"),
            use_passive_voice=data.get("use_passive_voice", True),
            include_examples=data.get("include_examples", True),
            include_caution_notes=data.get("include_caution_notes", True),
            section_order_preference=data.get("section_order_preference", []),
            custom_vocabulary=data.get("custom_vocabulary", {}),
            avoid_phrases=data.get("avoid_phrases", []),
            confidence=data.get("confidence", 0.0),
            sample_count=data.get("sample_count", 0),
            last_updated=data.get("last_updated", ""),
        )

    def merge_update(self, updates: Dict[str, Any]) -> None:
        """Merge partial updates, incrementing sample_count and confidence."""
        for key, value in updates.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.sample_count += 1
        self.confidence = min(1.0, self.sample_count / 20.0)  # Max at 20 samples
        from datetime import datetime
        self.last_updated = datetime.now().isoformat()


@dataclass
class Profile:
    """
    用户画像

    包含用户的写作偏好、审查标准和从文档学习的领域知识。
    核心数据结构为三元组 (subject, relation, object)，可直接迁移到图数据库。

    JSON 存储示例：
    {
      "triples": [
        {"s": "M12螺栓拧紧", "r": "力矩", "o": "45±5 N·m"},
        {"s": "热处理", "r": "温度", "o": "800-850°C"},
        {"s": "装配工艺", "r": "使用", "o": "对角交叉拧紧"}
      ]
    }

    图谱迁移映射：
    - triples[i].s → Node(:Entity {name})
    - triples[i].r → Edge(:RELATION {type})
    - triples[i].o → Node(:Value {name}) 或 Node(:Entity {name})
    """
    id: str
    user_id: str
    domain: str  # assembly, welding, coating, etc.
    writing: WritingConfig = field(default_factory=WritingConfig)
    review: ReviewConfig = field(default_factory=ReviewConfig)
    preferences: WritingPreferences = field(default_factory=WritingPreferences)

    # Domain knowledge: triple structure (graph-ready)
    triples: List[Dict[str, str]] = field(default_factory=list)

    # Kept for backward compat and quick term lookup
    frequent_terms: Dict[str, int] = field(default_factory=dict)

    ai_generated_summary: str = ""
    source_document_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "domain": self.domain,
            "writing": self.writing.to_dict(),
            "review": self.review.to_dict(),
            "preferences": self.preferences.to_dict(),
            "triples": self.triples,
            "frequent_terms": self.frequent_terms,
            "ai_generated_summary": self.ai_generated_summary,
            "source_document_ids": self.source_document_ids,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Profile":
        prefs_data = data.get("preferences", {})
        if not prefs_data and any(k in data for k in ["preferred_sentence_length", "custom_vocabulary"]):
            prefs_data = {k: data[k] for k in data if k in [
                "preferred_sentence_length", "use_passive_voice",
                "include_examples", "include_caution_notes",
                "custom_vocabulary", "avoid_phrases",
            ]}
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            user_id=data.get("user_id", "default"),
            domain=data.get("domain", "assembly"),
            writing=WritingConfig.from_dict(data.get("writing", {})),
            review=ReviewConfig.from_dict(data.get("review", {})),
            preferences=WritingPreferences.from_dict(prefs_data),
            triples=data.get("triples", []),
            frequent_terms=data.get("frequent_terms", {}),
            ai_generated_summary=data.get("ai_generated_summary", ""),
            source_document_ids=data.get("source_document_ids", []),
        )

    def to_context_text(self, max_tokens: int = 300) -> str:
        """Render profile as context text for LLM injection."""
        parts: List[str] = []
        parts.append(f"领域: {self.domain}")
        parts.append(f"语气: {self.writing.tone}, 详细程度: {self.writing.detail_level}")

        if self.ai_generated_summary:
            parts.append(f"画像摘要: {self.ai_generated_summary}")

        # Render top triples as structured knowledge
        if self.triples:
            triple_lines = []
            for t in self.triples[:30]:
                triple_lines.append(f"- {t['s']} [{t['r']}] {t['o']}")
            parts.append("领域知识:\n" + "\n".join(triple_lines))

        return "\n".join(parts)
    
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
