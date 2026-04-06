"""
任务管理API
提供任务创建、查询、对话等REST接口
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from datetime import datetime

from app.shared.logging import get_logger
from app.repositories import get_repository, reset_repository
from app.services.context_manager import ContextManager
from app.services.context_builder import ContextBuilder

logger = get_logger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ============ Pydantic Models ============

class CreateTaskRequest(BaseModel):
    """创建任务请求"""
    task_name: str = Field(..., description="任务名称", min_length=1, max_length=100)
    task_type: str = Field(default="craft_document_edit", description="任务类型")
    source_docs: Optional[List[str]] = Field(default=None, description="关联的源文档")
    tags: Optional[List[str]] = Field(default=None, description="标签")


class SendMessageRequest(BaseModel):
    """发送消息请求"""
    content: str = Field(..., description="消息内容", min_length=1)
    role: str = Field(default="user", description="角色: user/assistant/system")
    metadata: Optional[dict] = Field(default=None, description="元数据")


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str
    task_name: str
    task_type: str
    status: str
    created_at: str
    updated_at: str
    source_documents: List[str] = []
    tags: List[str] = []


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: List[TaskResponse]
    total: int


class MessageResponse(BaseModel):
    """消息响应"""
    id: str
    role: str
    content: str
    timestamp: str
    metadata: Optional[dict] = None


class ContextResponse(BaseModel):
    """上下文响应"""
    task_id: str
    context: str
    token_estimate: int


# ============ Dependencies ============

def get_task_repository():
    """获取任务Repository"""
    return get_repository()


def get_context_manager():
    """获取上下文管理器"""
    return ContextManager()


def get_context_builder():
    """获取上下文构建器"""
    return ContextBuilder(repository=get_task_repository())


# ============ API Endpoints ============

@router.post("", response_model=TaskResponse, summary="创建新任务")
async def create_task(
    request: CreateTaskRequest,
    repo = Depends(get_task_repository),
):
    """
    创建新的工艺编辑任务

    - **task_name**: 任务名称，如"电缆装配编辑"
    - **task_type**: 任务类型，默认"craft_document_edit"
    - **source_docs**: 关联的源文档列表
    - **tags**: 标签列表
    """
    try:
        task_id = repo.create_task(
            task_name=request.task_name,
            task_type=request.task_type,
            source_docs=request.source_docs,
            tags=request.tags,
        )

        meta = repo.get_meta(task_id)

        logger.info(
            "api_task_created",
            task_id=task_id,
            task_name=request.task_name,
        )

        return TaskResponse(
            task_id=meta.task_id,
            task_name=meta.task_name,
            task_type=meta.task_type,
            status=meta.status.value,
            created_at=meta.created_at.isoformat(),
            updated_at=meta.updated_at.isoformat(),
            source_documents=meta.source_documents,
            tags=meta.tags,
        )

    except Exception as e:
        logger.error("api_create_task_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=TaskListResponse, summary="获取任务列表")
async def list_tasks(
    status: Optional[str] = Query(None, description="按状态过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    repo = Depends(get_task_repository),
):
    """
    获取任务列表

    - **status**: 按状态过滤（pending/in_progress/completed/error）
    - **limit**: 返回数量
    - **offset**: 偏移量
    """
    from app.models.task_memory import TaskStatus

    status_enum = None
    if status:
        try:
            status_enum = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    tasks = repo.list_tasks(status=status_enum, limit=limit, offset=offset)

    task_responses = [
        TaskResponse(
            task_id=t.task_id,
            task_name=t.task_name,
            task_type=t.task_type,
            status=t.status.value,
            created_at=t.created_at.isoformat(),
            updated_at=t.updated_at.isoformat(),
            source_documents=t.source_documents,
            tags=t.tags,
        )
        for t in tasks
    ]

    return TaskListResponse(
        tasks=task_responses,
        total=len(task_responses),  # 实际应该查询总数
    )


@router.get("/{task_id}", response_model=TaskResponse, summary="获取任务信息")
async def get_task(
    task_id: str,
    repo = Depends(get_task_repository),
):
    """
    获取任务详细信息

    - **task_id**: 任务ID
    """
    meta = repo.get_meta(task_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return TaskResponse(
        task_id=meta.task_id,
        task_name=meta.task_name,
        task_type=meta.task_type,
        status=meta.status.value,
        created_at=meta.created_at.isoformat(),
        updated_at=meta.updated_at.isoformat(),
        source_documents=meta.source_documents,
        tags=meta.tags,
    )


@router.delete("/{task_id}", summary="删除任务")
async def delete_task(
    task_id: str,
    repo = Depends(get_task_repository),
):
    """
    删除任务

    - **task_id**: 任务ID
    """
    if not repo.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    success = repo.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete task")

    logger.info("api_task_deleted", task_id=task_id)

    return {"success": True, "task_id": task_id}


@router.get("/{task_id}/messages", response_model=List[MessageResponse], summary="获取对话历史")
async def get_messages(
    task_id: str,
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    repo = Depends(get_task_repository),
):
    """
    获取任务的对话历史

    - **task_id**: 任务ID
    - **limit**: 返回数量
    - **offset**: 偏移量
    """
    if not repo.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    messages = repo.get_messages(task_id, limit=limit, offset=offset)

    return [
        MessageResponse(
            id=m.id,
            role=m.role.value if hasattr(m.role, "value") else str(m.role),
            content=m.content,
            timestamp=m.timestamp.isoformat() if hasattr(m.timestamp, "isoformat") else str(m.timestamp),
            metadata=m.metadata,
        )
        for m in messages
    ]


@router.post("/{task_id}/messages", response_model=MessageResponse, summary="发送消息")
async def send_message(
    task_id: str,
    request: SendMessageRequest,
    repo = Depends(get_task_repository),
):
    """
    向任务发送消息

    - **task_id**: 任务ID
    - **content**: 消息内容
    - **role**: 角色（默认user）
    - **metadata**: 元数据
    """
    if not repo.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    message_id = repo.add_message(
        task_id=task_id,
        role=request.role,
        content=request.content,
        metadata=request.metadata,
    )

    # 获取刚添加的消息
    messages = repo.get_messages(task_id, limit=1, offset=0)
    if messages:
        m = messages[-1]
        return MessageResponse(
            id=m.id,
            role=m.role.value if hasattr(m.role, "value") else str(m.role),
            content=m.content,
            timestamp=m.timestamp.isoformat() if hasattr(m.timestamp, "isoformat") else str(m.timestamp),
            metadata=m.metadata,
        )

    return MessageResponse(
        id=message_id,
        role=request.role,
        content=request.content,
        timestamp=datetime.now().isoformat(),
        metadata=request.metadata,
    )


@router.get("/{task_id}/decisions", summary="获取决策记录")
async def get_decisions(
    task_id: str,
    repo = Depends(get_task_repository),
):
    """
    获取任务的决策记录

    - **task_id**: 任务ID
    """
    if not repo.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    decisions = repo.get_decisions(task_id)

    return [
        {
            "id": d.id,
            "type": d.decision_type.value if hasattr(d.decision_type, "value") else str(d.decision_type),
            "context": d.context,
            "selected": d.selected,
            "reason": d.reason,
            "user_confirmed": d.user_confirmed,
            "timestamp": d.timestamp.isoformat() if hasattr(d.timestamp, "isoformat") else str(d.timestamp),
        }
        for d in decisions
    ]


@router.get("/{task_id}/context", response_model=ContextResponse, summary="获取任务上下文")
async def get_context(
    task_id: str,
    include_documents: bool = Query(True, description="是否包含源文档"),
    include_history: bool = Query(True, description="是否包含对话历史"),
    max_history_turns: int = Query(10, ge=1, le=50, description="最大历史轮次"),
    repo = Depends(get_task_repository),
    context_builder = Depends(get_context_builder),
):
    """
    获取任务的完整上下文（用于LLM）

    - **task_id**: 任务ID
    - **include_documents**: 是否包含源文档
    - **include_history**: 是否包含对话历史
    - **max_history_turns**: 最大历史轮次
    """
    if not repo.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    context = context_builder.build_context(
        task_id=task_id,
        include_documents=include_documents,
        include_history=include_history,
        max_history_turns=max_history_turns,
    )

    token_estimate = context_builder.estimate_tokens(context)

    return ContextResponse(
        task_id=task_id,
        context=context,
        token_estimate=token_estimate,
    )


@router.get("/{task_id}/state", summary="获取任务状态")
async def get_state(
    task_id: str,
    repo = Depends(get_task_repository),
):
    """
    获取任务的当前状态

    - **task_id**: 任务ID
    """
    if not repo.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    state = repo.get_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"State not found for task: {task_id}")

    return {
        "task_id": task_id,
        "current_state": state.current_state.value if hasattr(state.current_state, "value") else str(state.current_state),
        "pending_action": state.pending_action,
        "context": state.context,
        "history_count": len(state.state_history),
    }


@router.get("/{task_id}/artifacts", summary="获取artifacts目录")
async def get_artifacts_dir(
    task_id: str,
    repo = Depends(get_task_repository),
):
    """
    获取任务的artifacts目录路径

    - **task_id**: 任务ID
    """
    if not repo.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    artifacts_dir = repo.get_artifacts_dir(task_id)

    return {
        "task_id": task_id,
        "artifacts_dir": artifacts_dir,
    }


# ============ 交互式对话API ============

class ContinueConversationRequest(BaseModel):
    """继续对话请求"""
    task_id: str = Field(..., description="任务ID")
    response_type: str = Field(default="text", description="响应类型: text/image/file/folder")
    content: str | List[str] | dict = Field(..., description="响应内容")
    selected_option: Optional[str] = Field(default=None, description="选择的选项")
    additional_info: Optional[dict] = Field(default=None, description="附加信息")


class ContinueConversationResponse(BaseModel):
    """继续对话响应"""
    success: bool
    action: str  # continue_assessment, start_execution, request_modification, cancel
    message: Optional[str] = None
    interaction: Optional[dict] = None  # 下一个交互消息（如果有）


class ProofreadRequest(BaseModel):
    """独立校对请求"""
    content: str = Field(..., description="待校对内容")
    check_type: str = Field(default="all", description="检查类型")
    target_standard: str = Field(default="enterprise_standard", description="目标标准")


class ReviewRequest(BaseModel):
    """独立审查请求"""
    content: str = Field(..., description="待审查内容")
    check_type: str = Field(default="all", description="检查类型")
    standards: str = Field(default="enterprise,safety", description="审查标准")


class AgentResultResponse(BaseModel):
    """Agent执行结果响应"""
    success: bool
    result: Optional[str] = None
    issues: List[dict] = []
    suggestions: List[str] = []


class ConversationStatusResponse(BaseModel):
    """对话状态响应"""
    task_id: str
    is_awaiting_input: bool
    pending_interaction: Optional[dict] = None
    current_state: str


def get_orchestrator():
    """获取Orchestrator实例"""
    from app.agents.orchestrator.orchestrator import ProcessOrchestrator
    return ProcessOrchestrator()


@router.post("/conversation/continue", response_model=ContinueConversationResponse, summary="继续对话")
async def continue_conversation(
    request: ContinueConversationRequest,
    repo = Depends(get_task_repository),
    orchestrator = Depends(get_orchestrator),
):
    """
    继续对话（用户补充信息后）

    - **task_id**: 任务ID
    - **response_type**: 响应类型 (text/image/file/folder)
    - **content**: 响应内容
    - **selected_option**: 选择的选项（如果是从选项中选择）
    - **additional_info**: 附加信息
    """
    from app.agents.orchestrator.interaction_models import UserResponse, InputType

    if not repo.task_exists(request.task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {request.task_id}")

    try:
        # 构建用户响应
        response_type_map = {
            "text": InputType.TEXT,
            "image": InputType.IMAGE,
            "file": InputType.FILE,
            "folder": InputType.FOLDER,
        }
        input_type = response_type_map.get(request.response_type, InputType.TEXT)

        user_response = UserResponse(
            session_id=request.task_id,
            response_type=input_type,
            content=request.content,
            selected_option=request.selected_option,
            additional_info=request.additional_info,
        )

        # 继续对话
        result = await orchestrator.continue_conversation(request.task_id, user_response)

        logger.info(
            "conversation_continued",
            task_id=request.task_id,
            action=result.get("action"),
        )

        return ContinueConversationResponse(
            success=result.get("success", True),
            action=result.get("action", "unknown"),
            message=result.get("message"),
            interaction=result.get("interaction"),
        )

    except Exception as e:
        logger.error("continue_conversation_failed", task_id=request.task_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proofread", response_model=AgentResultResponse, summary="独立校对")
async def proofread_content(
    request: ProofreadRequest,
    orchestrator = Depends(get_orchestrator),
):
    """
    独立调用校对Agent

    - **content**: 待校对内容
    - **check_type**: 检查类型 (all/terminology/format/consistency)
    - **target_standard**: 目标标准
    """
    try:
        result = await orchestrator.proofread_only(
            content=request.content,
            check_type=request.check_type,
            target_standard=request.target_standard,
        )

        logger.info(
            "proofread_completed",
            check_type=request.check_type,
            success=result.get("success", False),
        )

        return AgentResultResponse(
            success=result.get("success", False),
            result=result.get("result"),
            issues=result.get("issues", []),
            suggestions=result.get("suggestions", []),
        )

    except Exception as e:
        logger.error("proofread_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review", response_model=AgentResultResponse, summary="独立审查")
async def review_content(
    request: ReviewRequest,
    orchestrator = Depends(get_orchestrator),
):
    """
    独立调用审查Agent

    - **content**: 待审查内容
    - **check_type**: 检查类型 (all/compliance/safety/process)
    - **standards**: 审查标准（逗号分隔）
    """
    try:
        standards_list = [s.strip() for s in request.standards.split(",") if s.strip()]

        result = await orchestrator.review_only(
            content=request.content,
            check_type=request.check_type,
            standards=standards_list,
        )

        logger.info(
            "review_completed",
            check_type=request.check_type,
            standards=standards_list,
            success=result.get("success", False),
        )

        return AgentResultResponse(
            success=result.get("success", False),
            result=result.get("result"),
            issues=result.get("issues", []),
            suggestions=result.get("suggestions", []),
        )

    except Exception as e:
        logger.error("review_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation/{task_id}/status", response_model=ConversationStatusResponse, summary="获取对话状态")
async def get_conversation_status(
    task_id: str,
    repo = Depends(get_task_repository),
    orchestrator = Depends(get_orchestrator),
):
    """
    获取当前交互状态

    - **task_id**: 任务ID
    """
    if not repo.task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    try:
        status = await orchestrator.get_interaction_status(task_id)

        return ConversationStatusResponse(
            task_id=task_id,
            is_awaiting_input=status.get("is_awaiting_input", False),
            pending_interaction=status.get("pending_interaction"),
            current_state=status.get("current_state", "unknown"),
        )

    except Exception as e:
        logger.error("get_conversation_status_failed", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
