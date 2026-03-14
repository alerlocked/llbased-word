"""
Pydantic models for data validation and structure
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class TaskPlan(BaseModel):
    """
    任务执行计划模型
    """
    user_intent: str = Field(..., description="用户原始意图的简要概括")
    outline: List[str] = Field(default=[], description="文章的骨架大纲段落")
    search_keywords_local: List[str] = Field(default=[], description="用于本地素材检索的关键词列表（人名、地名、事件名）")
    search_queries_web: List[str] = Field(default=[], description="用于网络搜索的查询语句列表（背景、数据、政策）")
    article_genre: str = Field(default="新闻报道", description="文章体裁（如：人物专访、深度报道、快讯）")
    visual_focus: str = Field(default="", description="稿件的视觉重点描述，指导配图")
    article_style_id: Optional[int] = Field(default=None, description="目标风格ID")
    structure_type: str = Field(default="general", description="文章结构类型")
    execution_instructions: str = Field(default="", description="给ContentWriter的具体执行指令")

class AgentState(BaseModel):
    """
    Agent 工作流状态模型 (用于API传输)
    """
    task_id: str
    current_step: str
    progress: int
    message: str
    data: Optional[Dict[str, Any]] = None


class QuestionOption(BaseModel):
    """问题选项模型"""
    id: str = Field(..., description="选项ID")
    text: str = Field(..., description="选项文本")
    description: Optional[str] = Field(None, description="选项说明（可选）")


class Question(BaseModel):
    """带选项的问题模型"""
    id: str = Field(..., description="问题ID")
    question: str = Field(..., description="问题文本")
    question_type: str = Field(..., description="问题类型：goal/audience/position/genre/focus")
    options: List[QuestionOption] = Field(default=[], description="选项列表")
    allow_custom: bool = Field(True, description="是否允许自定义答案")
    required: bool = Field(True, description="是否必填")


class MaterialItem(BaseModel):
    """素材项模型"""
    id: str = Field(..., description="素材ID")
    title: str = Field(..., description="素材标题")
    content: str = Field(..., description="素材内容摘要")
    source: str = Field(..., description="素材来源")
    material_type: str = Field(..., description="素材类型：pdf/docx/txt/search")
    value_description: str = Field(..., description="素材价值说明（为什么有用、如何使用）")
    priority: str = Field(..., description="优先级：high/medium/low")
    relevance_score: Optional[float] = Field(None, description="相关性评分（0-1）")


class MaterialReport(BaseModel):
    """素材报告模型"""
    materials: List[MaterialItem] = Field(..., description="素材列表（带价值说明）")
    recommendations: List[str] = Field(default=[], description="推荐使用的素材ID列表")
    priority_ranking: List[str] = Field(default=[], description="优先级排序的素材ID列表")
    summary: Optional[str] = Field(None, description="报告摘要")


class ReviewSuggestion(BaseModel):
    """评审建议模型"""
    id: str = Field(..., description="建议ID")
    description: str = Field(..., description="建议描述")
    example: Optional[str] = Field(None, description="修改示例")
    impact: Optional[str] = Field(None, description="预期效果")


class ReviewIssue(BaseModel):
    """评审问题模型"""
    id: str = Field(..., description="问题ID")
    type: str = Field(..., description="问题类型：content/structure/language/logic")
    severity: str = Field(..., description="严重程度：high/medium/low")
    location: str = Field(..., description="问题位置描述")
    description: str = Field(..., description="问题描述")
    suggestions: List[ReviewSuggestion] = Field(default=[], description="多个修改建议选项")


class ImprovementSuggestion(BaseModel):
    """完善建议模型"""
    id: str = Field(..., description="建议ID")
    title: str = Field(..., description="建议标题（不超过30字）")
    priority: str = Field(default="medium", description="优先级：high/medium/low")


class ImprovementSolution(BaseModel):
    """修改方案模型"""
    id: str = Field(..., description="方案ID")
    name: str = Field(..., description="方案名称（如'方案A'）")
    title: str = Field(..., description="方案标题")
    suggestions: List[ImprovementSuggestion] = Field(default=[], description="完善建议列表（建议标题不超过30字）")
    pros: Optional[str] = Field(None, description="优点（已废弃，不再使用）")
    cons: Optional[str] = Field(None, description="缺点（已废弃，不再使用）")
    recommended: bool = Field(default=False, description="是否推荐")


class TodoItem(BaseModel):
    """待办事项模型"""
    id: str = Field(..., description="待办ID")
    title: str = Field(..., description="待办标题")
    description: Optional[str] = Field(None, description="详细描述（可选）")
    status: str = Field(default="pending", description="状态：pending/completed")
    priority: str = Field(default="medium", description="优先级：high/medium/low")
    created_at: Optional[str] = Field(None, description="创建时间")


# ==================== 风格画像模型（六维深度解构）====================

class StyleOverview(BaseModel):
    """1. 风格概述（宏观定性）- 可执行约束"""
    summary: str = Field(..., description="风格概述描述（仅用于展示），如'河南小镇青年口语风'")
    tags: List[str] = Field(default=[], description="风格标签列表")
    # 可执行约束
    formality_constraint: Dict[str, Any] = Field(..., description="语气参数约束，如{'oral_ratio': 0.7, 'forbidden_connectors': ['综上所述', '总而言之']}")
    paragraph_constraint: Dict[str, Any] = Field(default={}, description="段落约束，如{'max_lines': 3, 'avg_chars_per_para': 150}")


class Methodology(BaseModel):
    """2. 创作方法论（写作套路）- 可执行规则"""
    approach: str = Field(..., description="核心方法描述（仅用于展示），如'产品经理视角切入+生活化类比'")
    # 可执行规则
    analogy_rule: Dict[str, Any] = Field(..., description="类比规则：{'required': True, 'object_priority': ['product', 'nature', 'daily'], 'frequency_per_point': 1}")
    structure_template: Optional[str] = Field(None, description="结构模板，如'问题-分析-解决方案'")
    mandatory_patterns: List[str] = Field(default=[], description="强制要求的模式列表")


class ThinkingCore(BaseModel):
    """3. 思维内核（底层价值观）- 价值判断函数"""
    values: List[str] = Field(default=[], description="核心价值观描述（仅用于展示），如['成长导向', '效率优先']")
    # 可执行约束
    value_judgment_function: Dict[str, Any] = Field(..., description="价值判断函数：{'conflict_resolution': 'improvement_over_criticism', 'case_weight': {'personal_growth': 0.6, 'industry_data': 0.4}}")
    logic_patterns: List[str] = Field(default=[], description="强制逻辑模式，如['因果分析', '对比论证']")
    argumentation_rules: Dict[str, Any] = Field(default={}, description="论证规则约束")


class ExpressionFeatures(BaseModel):
    """4. 表达特征（语言指纹）- 句式约束参数"""
    sentence_length_ratio: Dict[str, float] = Field(default={}, description="句式长短比统计")
    # 可执行约束
    sentence_constraints: Dict[str, Any] = Field(..., description="句式约束：{'short_sentence_ratio': 0.4, 'max_length': 15, 'forbidden_patterns': ['一方面...另一方面...']}")
    opening_habits: List[str] = Field(default=[], description="开场习惯统计")
    keywords: List[str] = Field(default=[], description="高频词")
    formality_level: str = Field(default="半正式", description="正式程度")


class WritingHabits(BaseModel):
    """5. 创作习惯（行为模式）- 模板库和禁止规则"""
    opening_phrases: List[str] = Field(..., description="开场短语模板库：['说实话...', '这两天...', '有个现象...']")
    # 可执行约束
    opening_rule: Dict[str, Any] = Field(..., description="开场规则：{'use_template_only': True, 'forbid_innovation': True, 'random_select': True}")
    transition_patterns: List[str] = Field(default=[], description="过渡模式模板")
    closing_patterns: List[str] = Field(default=[], description="结尾模式模板")
    paragraph_length_preference: Optional[str] = Field(None, description="段落长度偏好")


class UniqueMarkers(BaseModel):
    """6. 独特标记（身份烙印）- 身份锚定框架"""
    background: Optional[str] = Field(None, description="背景信息（仅用于展示）")
    expertise: List[str] = Field(default=[], description="专业领域")
    # 可执行约束
    identity_framework: Dict[str, Any] = Field(..., description="身份锚定框架：{'default_analysis_framework': 'user-need-scene', 'mandatory_terms': ['迭代', '闭环'], 'term_density_per_1k': 3}")
    perspective_rules: List[str] = Field(default=[], description="视角规则，如['分析问题时使用产品经理视角']")


class StylePortrait(BaseModel):
    """风格画像模型 - 六维深度解构（完整Schema定义，可执行约束）"""
    # 六个核心维度
    style_overview: StyleOverview = Field(..., description="风格概述（含可执行约束）")
    methodology: Methodology = Field(..., description="创作方法论（含可执行规则）")
    thinking_core: ThinkingCore = Field(..., description="思维内核（含价值判断函数）")
    expression_features: ExpressionFeatures = Field(..., description="表达特征（含句式约束参数）")
    writing_habits: WritingHabits = Field(..., description="创作习惯（含模板库和禁止规则）")
    unique_markers: UniqueMarkers = Field(..., description="独特标记（含身份锚定框架）")
    
    # 元数据
    version: int = Field(default=1, description="版本号（支持进化）")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度（0-1）")
    last_updated: Optional[datetime] = Field(default=None, description="最后更新时间")
    source: str = Field(default="auto", description="来源：auto（自动生成）/manual（手动创建）/hybrid（混合）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "style_overview": {
                    "summary": "河南小镇青年口语风",
                    "tags": ["接地气", "口语化", "生活化"],
                    "formality_constraint": {
                        "oral_ratio": 0.7,
                        "forbidden_connectors": ["综上所述", "总而言之"]
                    },
                    "paragraph_constraint": {
                        "max_lines": 3,
                        "avg_chars_per_para": 150
                    }
                },
                "methodology": {
                    "approach": "产品经理视角切入+生活化类比",
                    "analogy_rule": {
                        "required": True,
                        "object_priority": ["product", "nature", "daily"],
                        "frequency_per_point": 1
                    },
                    "structure_template": "问题-分析-解决方案"
                },
                "thinking_core": {
                    "values": ["成长导向", "效率优先"],
                    "value_judgment_function": {
                        "conflict_resolution": "improvement_over_criticism",
                        "case_weight": {
                            "personal_growth": 0.6,
                            "industry_data": 0.4
                        }
                    },
                    "logic_patterns": ["因果分析", "对比论证"]
                }
            }
        }


# ==================== ModePolicy 模式策略模型（工作台核心）====================

class BoundaryConfig(BaseModel):
    """边界约束配置"""
    must_include: List[str] = Field(default=[], description="必须包含的要点列表")
    must_avoid: List[str] = Field(default=[], description="必须避免的禁区列表（敏感词/话题/表述）")
    sensitive_topics: List[str] = Field(default=[], description="敏感话题列表（需要特别提示）")
    tone_guardrails: List[str] = Field(default=[], description="语气护栏（如：不得讽刺、保持中立）")


class EvidencePolicy(BaseModel):
    """证据与引用策略"""
    priority: List[str] = Field(
        default=["user_materials", "trusted_web", "open_web"],
        description="证据来源优先级（interview/user_materials/trusted_web/open_web/rag）"
    )
    require_citations: bool = Field(default=True, description="是否强制要求引用")
    citation_style: str = Field(default="inline", description="引用风格：inline/footnote/endnote")
    allow_uncited_claims: str = Field(default="rare", description="允许无引用声明的程度：never/rare/common")
    trusted_sources_allowlist: List[str] = Field(default=[], description="可信来源白名单（域名/机构）")
    untrusted_sources_blocklist: List[str] = Field(default=[], description="不可信来源黑名单")


class ReviewPolicy(BaseModel):
    """审查与校对策略"""
    enable_style_review: bool = Field(default=True, description="是否启用风格审查")
    enable_fact_review: bool = Field(default=True, description="是否启用事实审查")
    fact_severity_threshold_to_block: str = Field(
        default="high",
        description="事实问题严重度阈值（超过则阻塞）：low/medium/high"
    )
    auto_retrieve_on_fact_gaps: bool = Field(
        default=True,
        description="当发现事实缺口时，是否自动触发 Retriever 补证据"
    )
    max_revision_loops: int = Field(default=3, description="最大修订轮次（防止死循环）")


class WritingPolicy(BaseModel):
    """写作风格与结构策略"""
    structure_hint: str = Field(
        default="general",
        description="结构提示：news_inverted_pyramid/research_report/creative_narrative/qa_format/general"
    )
    verbosity: str = Field(default="medium", description="详略程度：concise/medium/detailed")
    headline_style: str = Field(default="neutral", description="标题风格：strong/neutral/gentle")
    risk_disclosure_style: str = Field(
        default="balanced",
        description="风险披露风格：aggressive/balanced/gentle"
    )


class WorkflowPolicy(BaseModel):
    """工作流暂停点与确认策略"""
    require_user_confirm_boundaries: bool = Field(
        default=True,
        description="是否要求用户确认边界（Step1 暂停点）"
    )
    require_user_confirm_materials: bool = Field(
        default=True,
        description="是否要求用户确认素材清单（Step3 暂停点）"
    )
    require_user_confirm_before_publish: bool = Field(
        default=False,
        description="是否要求用户在发布前最终确认（Step6 暂停点）"
    )


class ModePolicy(BaseModel):
    """
    模式策略（可执行 JSON）
    核心：任务/场景级"作业规范"，约束"能不能写、写什么、用什么证据、怎么审查"
    """
    id: str = Field(..., description="策略唯一ID（如：preset.reporter.v1）")
    name: str = Field(..., description="策略名称（如：Reporter）")
    description: str = Field(..., description="策略描述（给用户看的简介）")
    mode: str = Field(
        ...,
        description="模式类型：reporter/researcher/creator/craft/fast_draft/publish_ready"
    )
    
    # 五大策略维度
    boundaries: BoundaryConfig = Field(default_factory=BoundaryConfig, description="边界约束配置")
    evidence_policy: EvidencePolicy = Field(default_factory=EvidencePolicy, description="证据与引用策略")
    review_policy: ReviewPolicy = Field(default_factory=ReviewPolicy, description="审查与校对策略")
    writing_policy: WritingPolicy = Field(default_factory=WritingPolicy, description="写作风格与结构策略")
    workflow_policy: WorkflowPolicy = Field(default_factory=WorkflowPolicy, description="工作流暂停点策略")
    
    # 元数据
    version: int = Field(default=1, description="策略版本号")
    is_preset: bool = Field(default=False, description="是否为内置预设")
    base_preset_id: Optional[str] = Field(None, description="基于哪个预设（用户自定义时）")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "preset.reporter.v1",
                "name": "Reporter",
                "description": "采访素材优先，敏感提示强，适合新闻稿与快讯。",
                "mode": "reporter",
                "boundaries": {
                    "must_include": [],
                    "must_avoid": ["未经证实的猜测"],
                    "sensitive_topics": ["政治敏感", "商业机密"],
                    "tone_guardrails": ["保持客观中立"]
                },
                "evidence_policy": {
                    "priority": ["interview", "user_materials", "trusted_web"],
                    "require_citations": True,
                    "citation_style": "inline"
                }
            }
        }


class PolicySummary(BaseModel):
    """
    策略摘要（给用户看的可读版）
    用于 Step1 边界确认时展示"当前使用的策略配置"
    """
    policy_id: str = Field(..., description="策略ID")
    policy_name: str = Field(..., description="策略名称")
    mode: str = Field(..., description="模式类型")
    key_constraints: List[str] = Field(default=[], description="关键约束列表（3-5条）")
    user_overrides: Dict[str, Any] = Field(default={}, description="用户覆盖的配置项")
    
    def generate_readable_text(self) -> str:
        """生成可读文本"""
        lines = [
            f"📋 当前策略：{self.policy_name} ({self.mode})",
            "",
            "关键约束："
        ]
        for idx, constraint in enumerate(self.key_constraints, 1):
            lines.append(f"  {idx}. {constraint}")
        
        if self.user_overrides:
            lines.append("")
            lines.append("⚙️ 自定义配置：")
            for key, value in self.user_overrides.items():
                lines.append(f"  - {key}: {value}")
        
        return "\n".join(lines)


# ==================== 预设策略常量（6个内置模板）====================

# 1. Reporter（记者）：快、抓要点、强敏感提示
PRESET_REPORTER = ModePolicy(
    id="preset.reporter.v1",
    name="Reporter",
    description="采访素材优先，敏感提示强，适合新闻稿与快讯。",
    mode="reporter",
    boundaries=BoundaryConfig(
        must_avoid=["未经证实的猜测", "情绪化表述"],
        sensitive_topics=["政治立场", "商业机密", "个人隐私"],
        tone_guardrails=["保持客观中立", "避免煽动性表述"]
    ),
    evidence_policy=EvidencePolicy(
        priority=["interview", "user_materials", "trusted_web", "open_web"],
        require_citations=True,
        citation_style="inline",
        allow_uncited_claims="rare"
    ),
    review_policy=ReviewPolicy(
        enable_style_review=True,
        enable_fact_review=True,
        fact_severity_threshold_to_block="medium",
        auto_retrieve_on_fact_gaps=True,
        max_revision_loops=2
    ),
    writing_policy=WritingPolicy(
        structure_hint="news_inverted_pyramid",
        verbosity="medium",
        headline_style="strong"
    ),
    workflow_policy=WorkflowPolicy(
        require_user_confirm_boundaries=True,
        require_user_confirm_materials=True
    ),
    is_preset=True
)

# 2. Researcher（研究者）：强证据、强引用、强可追溯
PRESET_RESEARCHER = ModePolicy(
    id="preset.researcher.v1",
    name="Researcher",
    description="强证据、强引用、强可追溯，适合研究报告与分析文章。",
    mode="researcher",
    boundaries=BoundaryConfig(
        must_include=["数据来源", "方法论说明"],
        must_avoid=["主观臆断", "无依据结论"],
        tone_guardrails=["严谨学术", "逻辑清晰"]
    ),
    evidence_policy=EvidencePolicy(
        priority=["rag", "user_materials", "trusted_web"],
        require_citations=True,
        citation_style="footnote",
        allow_uncited_claims="never"
    ),
    review_policy=ReviewPolicy(
        enable_style_review=True,
        enable_fact_review=True,
        fact_severity_threshold_to_block="low",  # 最严格
        auto_retrieve_on_fact_gaps=True,
        max_revision_loops=3
    ),
    writing_policy=WritingPolicy(
        structure_hint="research_report",
        verbosity="detailed",
        headline_style="neutral"
    ),
    workflow_policy=WorkflowPolicy(
        require_user_confirm_boundaries=True,
        require_user_confirm_materials=True,
        require_user_confirm_before_publish=True
    ),
    is_preset=True
)

# 3. Creator（创作者）：弱证据约束、重意图与情绪
PRESET_CREATOR = ModePolicy(
    id="preset.creator.v1",
    name="Creator",
    description="弱证据约束，重意图与情绪，适合创意写作与叙事文章。",
    mode="creator",
    boundaries=BoundaryConfig(
        must_avoid=["抄袭"],
        tone_guardrails=["保持一致的叙事视角"]
    ),
    evidence_policy=EvidencePolicy(
        priority=["user_materials", "open_web"],
        require_citations=False,
        allow_uncited_claims="common"
    ),
    review_policy=ReviewPolicy(
        enable_style_review=True,
        enable_fact_review=False,  # 创作模式不强制事实审查
        auto_retrieve_on_fact_gaps=False,
        max_revision_loops=2
    ),
    writing_policy=WritingPolicy(
        structure_hint="creative_narrative",
        verbosity="detailed",
        headline_style="gentle"
    ),
    workflow_policy=WorkflowPolicy(
        require_user_confirm_boundaries=False,
        require_user_confirm_materials=False
    ),
    is_preset=True
)

# 4. Craft（工艺）：强规范/参数硬约束、只允许权威/内部知识库
PRESET_CRAFT = ModePolicy(
    id="preset.craft.v1",
    name="Craft",
    description="强规范/参数硬约束，只认内部标准与权威库，适合技术文档与标准化流程。",
    mode="craft",
    boundaries=BoundaryConfig(
        must_include=["标准引用", "参数规格"],
        must_avoid=["主观推测", "非标准术语"],
        tone_guardrails=["严格遵循术语表", "格式统一"]
    ),
    evidence_policy=EvidencePolicy(
        priority=["rag", "user_materials"],  # 只认内部知识库
        require_citations=True,
        citation_style="inline",
        allow_uncited_claims="never"
    ),
    review_policy=ReviewPolicy(
        enable_style_review=True,
        enable_fact_review=True,
        fact_severity_threshold_to_block="low",
        auto_retrieve_on_fact_gaps=True,
        max_revision_loops=5  # 允许更多修订轮次
    ),
    writing_policy=WritingPolicy(
        structure_hint="general",
        verbosity="detailed",
        headline_style="neutral"
    ),
    workflow_policy=WorkflowPolicy(
        require_user_confirm_boundaries=True,
        require_user_confirm_materials=True,
        require_user_confirm_before_publish=True
    ),
    is_preset=True
)

# 5. FastDraft（快速草稿）：牺牲完备性换速度
PRESET_FAST_DRAFT = ModePolicy(
    id="preset.fast_draft.v1",
    name="FastDraft",
    description="牺牲完备性换速度，适合快速占位与草稿迭代。",
    mode="fast_draft",
    boundaries=BoundaryConfig(
        must_avoid=["明显错误"],
        tone_guardrails=[]
    ),
    evidence_policy=EvidencePolicy(
        priority=["user_materials", "open_web"],
        require_citations=False,
        allow_uncited_claims="common"
    ),
    review_policy=ReviewPolicy(
        enable_style_review=False,  # 跳过风格审查
        enable_fact_review=False,   # 跳过事实审查
        auto_retrieve_on_fact_gaps=False,
        max_revision_loops=1
    ),
    writing_policy=WritingPolicy(
        structure_hint="general",
        verbosity="concise",
        headline_style="neutral"
    ),
    workflow_policy=WorkflowPolicy(
        require_user_confirm_boundaries=False,
        require_user_confirm_materials=False
    ),
    is_preset=True
)

# 6. PublishReady（可发布严谨）：比 Researcher 更"保守"
PRESET_PUBLISH_READY = ModePolicy(
    id="preset.publish_ready.v1",
    name="PublishReady",
    description="比 Researcher 更保守，强制事实审查闭环，缺证据宁可删减。",
    mode="publish_ready",
    boundaries=BoundaryConfig(
        must_include=["来源标注", "免责声明"],
        must_avoid=["未验证信息", "争议性表述"],
        sensitive_topics=["法律风险", "医疗建议", "金融建议"],
        tone_guardrails=["保守严谨", "避免绝对化表述"]
    ),
    evidence_policy=EvidencePolicy(
        priority=["rag", "trusted_web", "user_materials"],
        require_citations=True,
        citation_style="footnote",
        allow_uncited_claims="never",
        trusted_sources_allowlist=[]  # 由用户配置
    ),
    review_policy=ReviewPolicy(
        enable_style_review=True,
        enable_fact_review=True,
        fact_severity_threshold_to_block="low",
        auto_retrieve_on_fact_gaps=True,
        max_revision_loops=5
    ),
    writing_policy=WritingPolicy(
        structure_hint="research_report",
        verbosity="detailed",
        headline_style="neutral",
        risk_disclosure_style="aggressive"
    ),
    workflow_policy=WorkflowPolicy(
        require_user_confirm_boundaries=True,
        require_user_confirm_materials=True,
        require_user_confirm_before_publish=True
    ),
    is_preset=True
)

# 预设策略字典（便于通过 mode 快速查找）
PRESET_POLICIES: Dict[str, ModePolicy] = {
    "reporter": PRESET_REPORTER,
    "researcher": PRESET_RESEARCHER,
    "creator": PRESET_CREATOR,
    "craft": PRESET_CRAFT,
    "fast_draft": PRESET_FAST_DRAFT,
    "publish_ready": PRESET_PUBLISH_READY,
}