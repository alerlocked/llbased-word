"""
任务记忆数据模型
定义任务级记忆系统的核心数据结构
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_REVIEW = "waiting_review"
    COMPLETED = "completed"
    ERROR = "error"


class ProcessState(str, Enum):
    """工艺文件编辑流程状态"""
    IDLE = "idle"
    INTENT_RECOGNITION = "intent_recognition"
    TASK_DECOMPOSITION = "task_decomposition"
    TASK_EXECUTION = "task_execution"
    RESULT_AGGREGATION = "result_aggregation"
    USER_REVIEW = "user_review"
    COMPLETION = "completion"
    ERROR = "error"


class StateTransition(BaseModel):
    """状态转换记录"""
    from_state: str
    to_state: str
    timestamp: datetime = Field(default_factory=datetime.now)
    trigger: Optional[str] = None  # 触发转换的原因或事件


class TaskMeta(BaseModel):
    """任务元数据"""
    task_id: str = Field(..., description="任务ID，格式: {任务名}_{时间戳}")
    task_name: str = Field(..., description="任务名称")
    task_type: str = Field(default="craft_document_edit", description="任务类型")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    source_documents: List[str] = Field(default_factory=list, description="关联的源文档")
    tags: List[str] = Field(default_factory=list, description="标签")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class TaskState(BaseModel):
    """任务状态机状态"""
    current_state: ProcessState = Field(default=ProcessState.IDLE, description="当前状态")
    state_history: List[StateTransition] = Field(default_factory=list, description="状态转换历史")
    pending_action: Optional[Dict[str, Any]] = Field(default=None, description="待执行动作")
    context: Dict[str, Any] = Field(default_factory=dict, description="状态上下文")


class MessageRole(str, Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """对话消息"""
    id: str = Field(..., description="消息ID")
    role: MessageRole = Field(..., description="角色")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据，如引用的表格、置信度等")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Conversation(BaseModel):
    """对话历史"""
    messages: List[Message] = Field(default_factory=list, description="消息列表")
    summary: Optional[str] = Field(default=None, description="对话摘要")


class DecisionType(str, Enum):
    """决策类型"""
    TOOL_SELECTION = "tool_selection"
    METHOD_CHOICE = "method_choice"
    PARAMETER_SETTING = "parameter_setting"
    DOCUMENT_APPROVAL = "document_approval"
    OTHER = "other"


class Decision(BaseModel):
    """决策记录"""
    id: str = Field(..., description="决策ID")
    decision_type: DecisionType = Field(..., description="决策类型")
    context: str = Field(..., description="决策上下文/问题描述")
    options: List[str] = Field(default_factory=list, description="可选方案")
    selected: str = Field(..., description="选择的方案")
    reason: str = Field(default="", description="选择原因")
    timestamp: datetime = Field(default_factory=datetime.now, description="决策时间")
    user_confirmed: bool = Field(default=False, description="是否经用户确认")
    source: str = Field(default="agent_suggestion", description="决策来源: agent_suggestion/user_input")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DecisionLog(BaseModel):
    """决策日志"""
    decisions: List[Decision] = Field(default_factory=list, description="决策列表")


class TaskContext(BaseModel):
    """任务上下文缓存"""
    task_id: str
    context_text: str = Field(default="", description="构建的上下文文本")
    document_summaries: Dict[str, str] = Field(default_factory=dict, description="文档摘要缓存")
    last_updated: datetime = Field(default_factory=datetime.now, description="最后更新时间")
    token_count: int = Field(default=0, description="Token数量估计")
