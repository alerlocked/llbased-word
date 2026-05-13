"""
Profile model - User profile with condition-grouped knowledge, principles, and preferences.

Data structure:
- ConditionGroup: Multi-dimensional knowledge entry (entity + conditions → attributes)
- Principle: Hard rule for compliance checking (pass/fail)
- Preference: Soft rule for quality alignment (learned from user behavior)
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime
import yaml
import uuid
import json


# ========================================
# Condition-Grouped Knowledge
# ========================================

@dataclass
class ConditionGroup:
    """
    A knowledge entry with multi-dimensional conditions.

    Example:
        entity: "螺栓"
        conditions: {"材质": "不锈钢", "牌号": "M2", "头型": "沉头"}
        attributes: {"力矩": "45±5 N·m", "工具": "扭矩扳手"}
        source: "QJ903-10B-2011"

    The conditions dict uniquely identifies this knowledge entry.
    Same entity with different conditions → different entries.
    """
    id: str = ""
    entity: str = ""
    conditions: Dict[str, str] = field(default_factory=dict)
    attributes: Dict[str, str] = field(default_factory=dict)
    source: str = ""  # standard document or file ID
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConditionGroup":
        return cls(
            id=data.get("id", ""),
            entity=data.get("entity", ""),
            conditions=data.get("conditions", {}),
            attributes=data.get("attributes", {}),
            source=data.get("source", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def matches_conditions(self, query: Dict[str, str]) -> bool:
        """Check if this entry matches all given conditions."""
        for key, value in query.items():
            if self.conditions.get(key) != value:
                return False
        return True

    def has_same_key(self, other: "ConditionGroup") -> bool:
        """Two entries are considered the same if entity + conditions match."""
        return self.entity == other.entity and self.conditions == other.attributes


# ========================================
# Principle (Hard Rule)
# ========================================

@dataclass
class Principle:
    """
    A hard compliance rule. All principles are mandatory — no severity levels.

    Dimensions:
    - text_compliance: Format, mandatory sections, numbering
    - data_validity: Data must be traceable to known standards
    - terminology: Consistent term usage, no semantic ambiguity
    """
    id: str = ""
    dimension: str = ""  # text_compliance | data_validity | terminology
    name: str = ""       # Short name, e.g. "章节完整性"
    description: str = ""  # What this rule checks
    check_expression: str = ""  # How to check (natural language for LLM, or structured query)
    enabled: bool = True
    source: str = ""  # standard document ID

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Principle":
        return cls(
            id=data.get("id", ""),
            dimension=data.get("dimension", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            check_expression=data.get("check_expression", ""),
            enabled=data.get("enabled", True),
            source=data.get("source", ""),
        )


# ========================================
# Preference (Soft Rule)
# ========================================

@dataclass
class Preference:
    """
    A learned preference from user behavior.

    Dimensions:
    - readability: How easy for reviewers to understand
    - executability: How easy for field workers to follow
    - style: Writing patterns (sentence structure, terminology usage)
    """
    id: str = ""
    dimension: str = ""  # readability | executability | style
    category: str = ""   # e.g. "sentence_structure", "tool_mention_order"
    description: str = ""  # What this preference prefers
    positive_examples: List[str] = field(default_factory=list)  # Good examples
    negative_examples: List[str] = field(default_factory=list)  # Bad examples
    learned_from: str = ""  # "document" | "user_correction" | "ab_choice"
    source_ids: List[str] = field(default_factory=list)  # Document/correction IDs
    confidence: float = 0.0
    sample_count: int = 0
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Preference":
        return cls(
            id=data.get("id", ""),
            dimension=data.get("dimension", ""),
            category=data.get("category", ""),
            description=data.get("description", ""),
            positive_examples=data.get("positive_examples", []),
            negative_examples=data.get("negative_examples", []),
            learned_from=data.get("learned_from", ""),
            source_ids=data.get("source_ids", []),
            confidence=data.get("confidence", 0.0),
            sample_count=data.get("sample_count", 0),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


# ========================================
# Writing/Review Config (kept for backward compat)
# ========================================

@dataclass
class WritingConfig:
    tone: str = "技术文档"
    terminology: str = "standard"
    detail_level: str = "详细"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WritingConfig":
        return cls(
            tone=data.get("tone", "技术文档"),
            terminology=data.get("terminology", "standard"),
            detail_level=data.get("detail_level", "详细"),
        )


@dataclass
class ReviewConfig:
    check_completeness: bool = True
    check_accuracy: bool = True
    allowed_deviation: float = 0.1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewConfig":
        return cls(
            check_completeness=data.get("check_completeness", True),
            check_accuracy=data.get("check_accuracy", True),
            allowed_deviation=data.get("allowed_deviation", 0.1),
        )


# ========================================
# Profile (Main Model)
# ========================================

@dataclass
class Profile:
    """
    User profile with condition-grouped knowledge, principles, and preferences.

    Legacy `triples` field kept for backward compat during migration.
    """
    id: str
    user_id: str
    domain: str

    # Config
    writing: WritingConfig = field(default_factory=WritingConfig)
    review: ReviewConfig = field(default_factory=ReviewConfig)

    # Knowledge: condition-grouped entries (replaces flat triples)
    knowledge: List[Dict[str, Any]] = field(default_factory=list)  # ConditionGroup dicts

    # Principles: hard rules for compliance
    principles: List[Dict[str, Any]] = field(default_factory=list)  # Principle dicts

    # Preferences: soft rules learned from user behavior
    preferences_list: List[Dict[str, Any]] = field(default_factory=list)  # Preference dicts

    # Frequent terms (kept for quick lookup)
    frequent_terms: Dict[str, int] = field(default_factory=dict)

    # AI summary
    ai_generated_summary: str = ""

    # Source tracking
    source_document_ids: List[str] = field(default_factory=list)

    # Legacy triples (for backward compat, will be migrated)
    triples: List[Dict[str, str]] = field(default_factory=list)

    # Legacy preferences flat structure
    preferences: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "domain": self.domain,
            "writing": self.writing.to_dict(),
            "review": self.review.to_dict(),
            "knowledge": self.knowledge,
            "principles": self.principles,
            "preferences_list": self.preferences_list,
            "frequent_terms": self.frequent_terms,
            "ai_generated_summary": self.ai_generated_summary,
            "source_document_ids": self.source_document_ids,
            # Legacy fields
            "triples": self.triples,
            "preferences": self.preferences,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Profile":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            user_id=data.get("user_id", "default"),
            domain=data.get("domain", "assembly"),
            writing=WritingConfig.from_dict(data.get("writing", {})),
            review=ReviewConfig.from_dict(data.get("review", {})),
            knowledge=data.get("knowledge", []),
            principles=data.get("principles", []),
            preferences_list=data.get("preferences_list", []),
            frequent_terms=data.get("frequent_terms", {}),
            ai_generated_summary=data.get("ai_generated_summary", ""),
            source_document_ids=data.get("source_document_ids", []),
            triples=data.get("triples", []),
            preferences=data.get("preferences", {}),
        )

    # --- Knowledge CRUD ---

    def add_knowledge(self, entry: ConditionGroup) -> str:
        """Add a knowledge entry. Returns ID. Deduplicates by entity+conditions."""
        for existing in self.knowledge:
            eg = ConditionGroup.from_dict(existing)
            if eg.entity == entry.entity and eg.conditions == entry.conditions:
                # Merge: update attributes, keep existing ID
                eg.attributes.update(entry.attributes)
                eg.updated_at = datetime.now().isoformat()
                eg.source = entry.source or eg.source
                existing.update(eg.to_dict())
                return eg.id
        self.knowledge.append(entry.to_dict())
        return entry.id

    def remove_knowledge(self, entry_id: str) -> bool:
        """Remove a knowledge entry by ID."""
        before = len(self.knowledge)
        self.knowledge = [k for k in self.knowledge if k.get("id") != entry_id]
        return len(self.knowledge) < before

    def find_knowledge(self, entity: str, conditions: Dict[str, str] | None = None) -> List[Dict[str, Any]]:
        """Find knowledge entries matching entity and optional conditions."""
        results = [k for k in self.knowledge if k.get("entity") == entity]
        if conditions:
            results = [k for k in results if ConditionGroup.from_dict(k).matches_conditions(conditions)]
        return results

    def merge_knowledge(self, source_entries: List[ConditionGroup]) -> int:
        """Merge multiple entries. Returns count of actually added (non-duplicate)."""
        added = 0
        for entry in source_entries:
            before = len(self.knowledge)
            self.add_knowledge(entry)
            if len(self.knowledge) > before:
                added += 1
        return added

    # --- Principle CRUD ---

    def add_principle(self, principle: Principle) -> str:
        """Add a principle. Deduplicates by name+dimension."""
        for existing in self.principles:
            if existing.get("name") == principle.name and existing.get("dimension") == principle.dimension:
                existing.update(principle.to_dict())
                return principle.id
        self.principles.append(principle.to_dict())
        return principle.id

    def remove_principle(self, principle_id: str) -> bool:
        before = len(self.principles)
        self.principles = [p for p in self.principles if p.get("id") != principle_id]
        return len(self.principles) < before

    # --- Preference CRUD ---

    def add_preference(self, pref: Preference) -> str:
        """Add a preference. Deduplicates by category+dimension."""
        for existing in self.preferences_list:
            if existing.get("category") == pref.category and existing.get("dimension") == pref.dimension:
                # Merge examples
                ep = Preference.from_dict(existing)
                ep.positive_examples = list(set(ep.positive_examples + pref.positive_examples))
                ep.negative_examples = list(set(ep.negative_examples + pref.negative_examples))
                ep.sample_count += pref.sample_count
                ep.confidence = min(1.0, ep.sample_count / 20.0)
                ep.updated_at = datetime.now().isoformat()
                existing.update(ep.to_dict())
                return ep.id
        self.preferences_list.append(pref.to_dict())
        return pref.id

    def remove_preference(self, pref_id: str) -> bool:
        before = len(self.preferences_list)
        self.preferences_list = [p for p in self.preferences_list if p.get("id") != pref_id]
        return len(self.preferences_list) < before

    # --- Context rendering ---

    def to_context_text(self, max_tokens: int = 500) -> str:
        """Render profile as context text for LLM injection."""
        parts: List[str] = []
        parts.append(f"领域: {self.domain}")
        parts.append(f"语气: {self.writing.tone}, 详细程度: {self.writing.detail_level}")

        if self.ai_generated_summary:
            parts.append(f"画像摘要: {self.ai_generated_summary}")

        # Render condition-grouped knowledge
        if self.knowledge:
            knowledge_lines = []
            for entry in self.knowledge[:30]:
                cg = ConditionGroup.from_dict(entry)
                cond_str = ", ".join(f"{k}={v}" for k, v in cg.conditions.items())
                attr_str = ", ".join(f"{k}={v}" for k, v in cg.attributes.items())
                if cond_str:
                    knowledge_lines.append(f"- {cg.entity} [{cond_str}]: {attr_str}")
                else:
                    knowledge_lines.append(f"- {cg.entity}: {attr_str}")
            parts.append("领域知识:\n" + "\n".join(knowledge_lines))

        # Render enabled principles
        enabled = [p for p in self.principles if p.get("enabled", True)]
        if enabled:
            principle_lines = [f"- {p['name']}: {p['description']}" for p in enabled[:20]]
            parts.append("审查原则:\n" + "\n".join(principle_lines))

        return "\n".join(parts)

    # --- Serialization ---

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "Profile":
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)

    def to_yaml(self, yaml_path: Path):
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.to_dict(), f, allow_unicode=True, default_flow_style=False)

    def to_json(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def from_json(cls, path: Path) -> "Profile":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)


# ========================================
# Default profiles
# ========================================

@dataclass
class WritingPreferences:
    """
    Dynamic writing preferences learned from user behavior.

    Loaded into WritingAgent for prompt injection. Updated via the
    Learning feedback loop (iteration diff extraction).
    """
    tone: str = "技术文档"
    terminology: str = "standard"
    detail_level: str = "详细"
    preferred_sentence_length: str = "medium"  # short / medium / long
    use_passive_voice: bool = True
    include_examples: bool = False
    include_caution_notes: bool = True
    avoid_phrases: List[str] = field(default_factory=list)
    custom_vocabulary: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0

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
            include_examples=data.get("include_examples", False),
            include_caution_notes=data.get("include_caution_notes", True),
            avoid_phrases=data.get("avoid_phrases", []),
            custom_vocabulary=data.get("custom_vocabulary", {}),
            confidence=data.get("confidence", 0.0),
        )

    @classmethod
    def from_profile(cls, profile: "Profile") -> "WritingPreferences":
        """Build WritingPreferences from a Profile's preferences_list."""
        prefs = cls()
        prefs.tone = profile.writing.tone
        prefs.detail_level = profile.writing.detail_level
        prefs.terminology = profile.writing.terminology

        for p_dict in profile.preferences_list:
            p = Preference.from_dict(p_dict)
            if p.dimension == "style" and p.confidence > 0.2:
                if p.category == "sentence_structure":
                    if "短句" in p.description:
                        prefs.preferred_sentence_length = "short"
                    elif "长句" in p.description:
                        prefs.preferred_sentence_length = "long"
                elif p.category == "voice":
                    prefs.use_passive_voice = "主动" not in p.description
                elif p.category == "avoid_phrases":
                    prefs.avoid_phrases.extend(p.negative_examples)
                elif p.category == "vocabulary":
                    prefs.custom_vocabulary.update(
                        dict(zip(p.positive_examples, p.positive_examples))
                    )
                prefs.confidence = max(prefs.confidence, p.confidence)

        # Legacy flat preferences
        flat = profile.preferences
        if "preferred_sentence_length" in flat:
            prefs.preferred_sentence_length = flat["preferred_sentence_length"]
        if "use_passive_voice" in flat:
            prefs.use_passive_voice = flat["use_passive_voice"]
        if "include_caution_notes" in flat:
            prefs.include_caution_notes = flat["include_caution_notes"]

        return prefs


def get_default_assembly_profile() -> Profile:
    """Default assembly process profile with built-in principles."""
    return Profile(
        id="default_assembly",
        user_id="default",
        domain="assembly",
        writing=WritingConfig(tone="技术文档", terminology="assembly", detail_level="详细"),
        review=ReviewConfig(check_completeness=True, check_accuracy=True, allowed_deviation=0.1),
        principles=[
            Principle(
                dimension="text_compliance",
                name="章节完整性",
                description="工艺文件必须包含完整章节结构",
                check_expression="检查文档是否包含所有必填章节",
            ).to_dict(),
            Principle(
                dimension="data_validity",
                name="数据可验证性",
                description="文档中的数据必须有可追溯来源，数值须与知识库条件组一致",
                check_expression="查找文档中的数值数据，验证是否与知识库中对应条件组的数据一致",
            ).to_dict(),
            Principle(
                dimension="terminology",
                name="术语一致性",
                description="同一文档中对同一事物必须使用统一的术语，不得混用",
                check_expression="检查文档中是否有同一概念使用不同术语的情况",
            ).to_dict(),
        ],
    )


def get_default_welding_profile() -> Profile:
    return Profile(
        id="default_welding",
        user_id="default",
        domain="welding",
        writing=WritingConfig(tone="技术文档", terminology="welding", detail_level="详细"),
        review=ReviewConfig(check_completeness=True, check_accuracy=True, allowed_deviation=0.1),
        principles=[
            Principle(
                dimension="text_compliance",
                name="章节完整性",
                description="焊接工艺文件必须包含完整章节结构",
            ).to_dict(),
            Principle(
                dimension="data_validity",
                name="数据可验证性",
                description="焊接参数必须有可追溯来源，数值须与知识库条件组一致",
            ).to_dict(),
        ],
    )
