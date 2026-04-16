"""
数据库模型定义
使用SQLAlchemy ORM
工艺文件辅助编辑系统
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, ForeignKey, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# 创建基类
Base = declarative_base()

class Project(Base):
    """项目表(用于管理音频文件) - 已废弃，保留用于兼容性"""
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, comment="项目名称")
    description = Column(Text, nullable=True, comment="项目描述")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

class KnowledgeCard(Base):
    """知识卡片表"""
    __tablename__ = "knowledge_cards"

    id = Column(Integer, primary_key=True, index=True)
    entity = Column(String(255), nullable=False, comment="实体名称")
    entity_type = Column(String(20), nullable=False, comment="实体类型: time/location/person/organization/history")
    description = Column(Text, nullable=False, comment="简要说明")
    sources = Column(JSON, default=[], comment="来源列表")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

class Material(Base):
    """素材表 - 只存储元数据，内容存储在文件系统"""
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, comment="素材名称")
    material_type = Column(String(20), nullable=False, comment="素材类型: pdf/docx/txt/search")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关系
    figures = relationship("Figure", back_populates="material", cascade="all, delete-orphan")
    pages = relationship("MaterialPage", back_populates="material", cascade="all, delete-orphan")

class MaterialPage(Base):
    """素材页表 - 只存储元数据（页码和图片路径）"""
    __tablename__ = "material_pages"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, comment="关联的素材ID")
    page_number = Column(Integer, nullable=False, comment="页码")
    image_path = Column(String(512), nullable=False, comment="图片文件路径")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 关系
    material = relationship("Material", back_populates="pages")

class CreationProject(Base):
    """创作项目表"""
    __tablename__ = "creation_projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, comment="项目名称")
    content = Column(Text, default="", comment="正式稿内容(富文本HTML)")
    material_ids = Column(JSON, default=[], comment="关联的素材ID列表")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关系
    uploaded_images = relationship("UploadedImage", back_populates="project")

class EditorVersion(Base):
    """编辑器版本历史表"""
    __tablename__ = "editor_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("creation_projects.id"), nullable=False, comment="项目ID")
    content = Column(Text, nullable=False, comment="内容")
    diff = Column(JSON, nullable=True, comment="与上一版本的差异")
    operation = Column(String(50), nullable=False, comment="操作类型: ai_draft/ai_rewrite/manual_edit")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

class SearchResult(Base):
    """检索结果表(存储检索结果作为素材)"""
    __tablename__ = "search_results"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("creation_projects.id"), nullable=True, comment="项目ID")
    title = Column(String(255), nullable=False, comment="标题")
    content = Column(Text, nullable=False, comment="内容")
    source = Column(String(255), nullable=True, comment="来源")
    search_type = Column(String(50), nullable=False, comment="检索类型: local/web/rag")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")


class Figure(Base):
    """图表/图片表（从文档中提取的图片）"""
    __tablename__ = "figures"
    
    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, comment="关联的素材ID")
    file_path = Column(String(512), nullable=False, comment="图片文件路径")
    caption = Column(Text, nullable=True, comment="图片描述（用于检索）")
    page_number = Column(Integer, nullable=True, comment="所在页码")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    
    # 关系
    material = relationship("Material", back_populates="figures")


class UserStyleProfile(Base):
    """用户风格档案表"""
    __tablename__ = "user_style_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False, comment="用户ID")
    style_profile = Column(JSON, nullable=False, comment="风格档案JSON")
    sample_article_ids = Column(JSON, default=[], comment="样本文章ID列表")
    confidence_score = Column(Float, default=0.0, comment="置信度分数")
    last_updated = Column(DateTime, default=datetime.utcnow, comment="最后更新时间")
    update_count = Column(Integer, default=0, comment="更新次数")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    # Phase 4: dynamic preference schema (WritingPreferences JSON)
    preference_schema = Column(JSON, default={}, comment="动态偏好 schema")


class StyleLearningLog(Base):
    """风格学习日志表"""
    __tablename__ = "style_learning_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, comment="用户ID")
    learning_type = Column(String(50), nullable=False, comment="学习类型: initial/edit/periodic")
    original_content = Column(Text, comment="原始内容")
    modified_content = Column(Text, comment="修改后内容")
    extracted_preferences = Column(JSON, comment="提取的偏好")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")


class Annotation(Base):
    """注释/批注表"""
    __tablename__ = "annotations"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("creation_projects.id"), nullable=False, comment="项目ID")
    position = Column(String(255), nullable=False, comment="段落ID或文本位置")
    content = Column(Text, nullable=False, comment="注释内容")
    annotation_type = Column(String(50), default="note", comment="类型：note/补充/引用/待办/修改建议")
    is_resolved = Column(Boolean, default=False, comment="是否已解决（用于待办类）")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")


class Citation(Base):
    """引用/参考文献表"""
    __tablename__ = "citations"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("creation_projects.id"), nullable=False, comment="项目ID")
    source_type = Column(String(50), nullable=False, comment="类型：document/web/expert/book")
    source_id = Column(Integer, nullable=True, comment="来源ID（关联到对应的素材）")
    content = Column(Text, nullable=False, comment="引用内容/摘录")
    author = Column(String(255), nullable=True, comment="作者/来源")
    title = Column(String(255), nullable=True, comment="标题/出处")
    date = Column(String(100), nullable=True, comment="日期")
    url = Column(String(512), nullable=True, comment="URL（网络来源）")
    position = Column(String(255), nullable=True, comment="在文章中的位置")
    citation_number = Column(Integer, nullable=True, comment="引用序号")
    format_style = Column(String(50), default="custom", comment="引用格式：APA/MLA/Chicago/GB7714/custom")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")


class ArticleFigure(Base):
    """文章图片关联表"""
    __tablename__ = "article_figures"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("creation_projects.id"), nullable=False, comment="项目ID")
    figure_id = Column(Integer, ForeignKey("figures.id"), nullable=True, comment="关联本地图片ID")
    web_image_id = Column(Integer, ForeignKey("web_images.id"), nullable=True, comment="关联网络图片ID")
    position = Column(String(255), nullable=False, comment="插入位置（段落ID或锚点）")
    caption = Column(Text, nullable=True, comment="图注/说明")
    figure_number = Column(Integer, nullable=False, comment="图序号（图1、图2...）")
    width = Column(Integer, nullable=True, comment="显示宽度（像素或百分比）")
    alignment = Column(String(20), default="center", comment="对齐方式：left/center/right")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")


class WebImage(Base):
    """网络图片表"""
    __tablename__ = "web_images"
    
    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(255), nullable=False, comment="搜索关键词")
    original_url = Column(String(512), nullable=False, comment="原始URL")
    thumbnail_url = Column(String(512), nullable=True, comment="缩略图URL")
    local_path = Column(String(512), nullable=False, comment="本地存储路径")
    title = Column(String(255), nullable=True, comment="图片标题")
    source_website = Column(String(255), nullable=True, comment="来源网站")
    width = Column(Integer, nullable=True, comment="宽度")
    height = Column(Integer, nullable=True, comment="高度")
    file_size = Column(Integer, nullable=True, comment="文件大小（字节）")
    file_hash = Column(String(64), unique=True, index=True, comment="文件哈希（MD5，用于去重）")
    relevance_score = Column(Float, nullable=True, comment="相关性评分（0-1，Qwen-VL评估）")
    description = Column(Text, nullable=True, comment="Qwen-VL生成的图片描述")
    is_verified = Column(Boolean, default=False, comment="是否经过质量验证")
    download_time = Column(DateTime, default=datetime.utcnow, comment="下载时间")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")


class UploadedImage(Base):
    """用户上传的图片表"""
    __tablename__ = "uploaded_images"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("creation_projects.id"), nullable=False, comment="所属项目ID（创作项目）")
    original_name = Column(String(255), nullable=False, comment="原始文件名")
    file_path = Column(String(512), nullable=False, comment="文件路径（相对于DATA_DIR）")
    file_hash = Column(String(64), unique=True, index=True, comment="文件哈希（MD5，用于去重）")
    file_size = Column(Integer, nullable=False, comment="文件大小（字节）")
    width = Column(Integer, nullable=True, comment="图片宽度（像素）")
    height = Column(Integer, nullable=True, comment="图片高度（像素）")
    keywords = Column(JSON, default=[], comment="AI生成的关键词列表")
    description = Column(Text, nullable=True, comment="AI生成的图片描述")
    caption = Column(String(255), nullable=True, comment="用户自定义标题")
    upload_time = Column(DateTime, default=datetime.utcnow, comment="上传时间")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    
    # 关系
    project = relationship("CreationProject", back_populates="uploaded_images")


class ConversationSession(Base):
    """对话会话表"""
    __tablename__ = "conversation_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, comment="用户ID（暂时不设置外键，后续可扩展）")
    project_id = Column(Integer, ForeignKey("creation_projects.id"), nullable=True, comment="项目ID")
    session_id = Column(String(64), unique=True, nullable=False, index=True, comment="会话ID（唯一标识）")
    current_step = Column(String(50), nullable=True, comment="当前步骤")
    state_data = Column(JSON, default={}, comment="存储 GraphState 状态数据")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")


class StyleProfile(Base):
    """风格档案表（从参考文本学习）"""
    __tablename__ = "style_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, comment="用户ID")
    scenario_name = Column(String(100), nullable=True, comment="业务场景名称")
    reference_texts = Column(JSON, default=[], comment="参考文本列表")
    style_features = Column(JSON, default={}, comment="风格特征（句式、用词、段落、语气等）")
    content_standards = Column(JSON, default={}, comment="内容标准（公司标准沉淀，暂不使用）")
    excellent_cases = Column(JSON, default=[], comment="优秀案例列表（暂不使用）")
    confidence_score = Column(Float, default=0.0, comment="学习置信度分数")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")


class NodeState:
    """
    节点状态枚举（PR1：状态机支持）
    
    状态定义：
    - IDLE: 空闲
    - ANALYZING: 需求分析中
    - AWAITING_SOLUTION: 等待选择改进方案
    - PLANNING: 规划中
    - AWAITING_PLAN: 等待选择计划
    - RETRIEVING: 检索中
    - WRITING: 撰写中
    - REVIEWING: 评审中
    - COMPLETED: 已完成
    """
    IDLE = "IDLE"
    ANALYZING = "ANALYZING"
    AWAITING_SOLUTION = "AWAITING_SOLUTION"
    PLANNING = "PLANNING"
    AWAITING_PLAN = "AWAITING_PLAN"
    RETRIEVING = "RETRIEVING"
    WRITING = "WRITING"
    REVIEWING = "REVIEWING"
    COMPLETED = "COMPLETED"


class NodeDocument(Base):
    """
    节点文档表
    存储每个关键工作节点的结构化输出文档
    用于持久化节点信息，避免超长上下文时丢失关键信息
    """
    __tablename__ = "node_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), nullable=False, index=True, comment="会话ID")
    node_name = Column(String(50), nullable=False, comment="节点名称（如analyze_node, planner_node等）")
    node_type = Column(String(20), nullable=False, comment="节点类型（analysis, planning, retrieval, writing, review）")
    document_data = Column(JSON, nullable=False, comment="结构化JSON数据（节点输入输出）")
    summary = Column(Text, nullable=True, comment="文档摘要（用于LTM语义检索）")
    meta_data = Column(JSON, default={}, comment="元数据（时间戳、置信度等）")
    created_at = Column(DateTime, default=datetime.utcnow, index=True, comment="创建时间")
    
    # PR1 新增字段：状态机和确定性路由支持
    state = Column(String(50), default="IDLE", nullable=False, comment="节点状态（IDLE/ANALYZING/AWAITING_SOLUTION/AWAITING_PLAN等）")
    options = Column(JSON, nullable=True, comment="待选项列表（方案ID/计划ID）")
    
    # PR5 新增字段：关键数据（延迟提取）
    key_data = Column(JSON, nullable=True, comment="关键数据（结构化提取，异步生成）")
    
    __table_args__ = (
        Index('idx_session_node', 'session_id', 'node_name'),
        Index('idx_session_type', 'session_id', 'node_type'),
        Index('idx_node_state', 'session_id', 'state'),  # PR1新增索引：支持快速查询状态
    )


class DraftDocument(Base):
    """工艺文件初稿表"""
    __tablename__ = "draft_documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), comment="文件标题")
    file_path = Column(String(512), comment="原始文件路径")
    file_type = Column(String(20), comment="文件类型: pdf/docx")
    parsed_content = Column(JSON, comment="解析后的结构化内容")
    content = Column(Text, default="", comment="当前最新内容（富文本HTML）")
    status = Column(String(20), default="draft", comment="状态: draft/completing/completed/archived")
    project_id = Column(Integer, ForeignKey("creation_projects.id"), nullable=True, comment="关联创作项目")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DraftVersion(Base):
    """版本快照表"""
    __tablename__ = "draft_versions"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("draft_documents.id"), nullable=False, index=True, comment="关联初稿ID")
    snapshot_content = Column(Text, comment="该快照的完整内容")
    snapshot_source = Column(String(20), comment="来源: ai_complete/user_edit/rollback")
    created_at = Column(DateTime, default=datetime.utcnow)
