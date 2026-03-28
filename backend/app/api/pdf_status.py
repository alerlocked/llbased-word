"""
PDF解析状态API

提供PDF解析队列的状态查询和管理接口
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel

from app.shared.logging import get_logger
from app.services.pdf_queue_manager import (
    get_pdf_queue_manager,
    PDFQueueManager,
    PDFTaskStatus,
    PDFTaskPriority
)
from app.services.pdf_watcher_service import (
    get_pdf_watcher_service,
    PDFWatcherService
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/pdf", tags=["PDF解析管理"])


# ============== 请求/响应模型 ==============

class AddPDFTaskRequest(BaseModel):
    """添加PDF任务请求"""
    source_path: str
    priority: Optional[str] = "NORMAL"
    force_reparse: Optional[bool] = False


class AddPDFTaskBatchRequest(BaseModel):
    """批量添加PDF任务请求"""
    source_paths: List[str]
    priority: Optional[str] = "NORMAL"


class AddWatchPathRequest(BaseModel):
    """添加监听路径请求"""
    path: str


class PDFTaskResponse(BaseModel):
    """PDF任务响应"""
    task_id: str
    source_path: str
    output_path: str
    file_hash: str
    file_size: int
    status: str
    priority: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    progress: int
    result: Optional[dict] = None


class QueueStatsResponse(BaseModel):
    """队列统计响应"""
    total_tasks: int
    pending_tasks: int
    processing_tasks: int
    completed_tasks: int
    failed_tasks: int
    active_workers: int
    max_workers: int


class WatcherStatusResponse(BaseModel):
    """监听服务状态响应"""
    is_running: bool
    watch_paths: List[str]
    scanned_files_count: int
    queue_stats: QueueStatsResponse


# ============== API路由 ==============

@router.get("/status", response_model=QueueStatsResponse)
async def get_queue_status():
    """
    获取队列状态

    Returns:
        队列统计信息
    """
    manager = get_pdf_queue_manager()
    stats = manager.get_stats()
    return QueueStatsResponse(**stats.to_dict())


@router.get("/tasks", response_model=List[PDFTaskResponse])
async def get_tasks(
    status: Optional[str] = Query(None, description="过滤状态"),
    limit: int = Query(50, ge=1, le=500, description="返回数量限制")
):
    """
    获取任务列表

    Args:
        status: 过滤状态 (pending/queued/processing/completed/failed/cancelled)
        limit: 返回数量限制

    Returns:
        任务列表
    """
    manager = get_pdf_queue_manager()

    status_enum = None
    if status:
        try:
            status_enum = PDFTaskStatus(status.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"无效的状态值: {status}"
            )

    tasks = manager.get_all_tasks(status=status_enum)
    tasks = tasks[:limit]

    return [
        PDFTaskResponse(**task.to_dict())
        for task in tasks
    ]


@router.get("/tasks/{task_id}", response_model=PDFTaskResponse)
async def get_task(task_id: str):
    """
    获取单个任务详情

    Args:
        task_id: 任务ID

    Returns:
        任务详情
    """
    manager = get_pdf_queue_manager()
    task = manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    return PDFTaskResponse(**task.to_dict())


@router.post("/tasks", response_model=PDFTaskResponse)
async def add_task(request: AddPDFTaskRequest):
    """
    添加PDF解析任务

    Args:
        request: 添加任务请求

    Returns:
        创建的任务信息
    """
    manager = get_pdf_queue_manager()

    # 解析优先级
    try:
        priority = PDFTaskPriority[request.priority.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"无效的优先级: {request.priority}"
        )

    task_id = await manager.add_task(
        source_path=request.source_path,
        priority=priority,
        force_reparse=request.force_reparse
    )

    if not task_id:
        # 文件可能已存在或解析完成
        existing_task = manager.get_task_by_path(request.source_path)
        if existing_task:
            return PDFTaskResponse(**existing_task.to_dict())
        raise HTTPException(
            status_code=400,
            detail="添加任务失败，请检查文件路径"
        )

    task = manager.get_task(task_id)
    return PDFTaskResponse(**task.to_dict())


@router.post("/tasks/batch", response_model=List[PDFTaskResponse])
async def add_tasks_batch(request: AddPDFTaskBatchRequest):
    """
    批量添加PDF解析任务

    Args:
        request: 批量添加任务请求

    Returns:
        成功添加的任务列表
    """
    manager = get_pdf_queue_manager()

    # 解析优先级
    try:
        priority = PDFTaskPriority[request.priority.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"无效的优先级: {request.priority}"
        )

    task_ids = await manager.add_tasks_batch(
        source_paths=request.source_paths,
        priority=priority
    )

    tasks = [manager.get_task(tid) for tid in task_ids]
    return [
        PDFTaskResponse(**task.to_dict())
        for task in tasks if task
    ]


@router.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """
    取消任务

    Args:
        task_id: 任务ID

    Returns:
        取消结果
    """
    manager = get_pdf_queue_manager()
    success = await manager.cancel_task(task_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    return {"success": True, "message": f"任务 {task_id} 已取消"}


@router.post("/cleanup")
async def cleanup_completed_tasks(
    older_than_hours: int = Query(24, ge=1, description="清理多少小时前完成的任务")
):
    """
    清理已完成的任务

    Args:
        older_than_hours: 清理多少小时前的任务

    Returns:
        清理结果
    """
    manager = get_pdf_queue_manager()
    manager.clear_completed_tasks(older_than_hours=older_than_hours)

    return {
        "success": True,
        "message": f"已清理 {older_than_hours} 小时前完成的任务"
    }


# ============== 监听服务API ==============

@router.get("/watcher/status", response_model=WatcherStatusResponse)
async def get_watcher_status():
    """
    获取监听服务状态

    Returns:
        监听服务状态信息
    """
    service = get_pdf_watcher_service()
    status = service.get_status()

    return WatcherStatusResponse(
        is_running=status["is_running"],
        watch_paths=status["watch_paths"],
        scanned_files_count=status["scanned_files_count"],
        queue_stats=QueueStatsResponse(**status["queue_stats"])
    )


@router.post("/watcher/start")
async def start_watcher(background_tasks: BackgroundTasks):
    """
    启动监听服务

    Returns:
        启动结果
    """
    service = get_pdf_watcher_service()

    if service._is_running:
        return {"success": True, "message": "监听服务已在运行"}

    background_tasks.add_task(service.start)

    return {"success": True, "message": "监听服务启动中"}


@router.post("/watcher/stop")
async def stop_watcher():
    """
    停止监听服务

    Returns:
        停止结果
    """
    service = get_pdf_watcher_service()
    await service.stop()

    return {"success": True, "message": "监听服务已停止"}


@router.post("/watcher/paths", response_model=WatcherStatusResponse)
async def add_watch_path(request: AddWatchPathRequest):
    """
    添加监听路径

    Args:
        request: 添加监听路径请求

    Returns:
        更新后的监听服务状态
    """
    service = get_pdf_watcher_service()
    service.add_watch_path(request.path)

    status = service.get_status()
    return WatcherStatusResponse(
        is_running=status["is_running"],
        watch_paths=status["watch_paths"],
        scanned_files_count=status["scanned_files_count"],
        queue_stats=QueueStatsResponse(**status["queue_stats"])
    )


@router.delete("/watcher/paths")
async def remove_watch_path(path: str = Query(..., description="要移除的监听路径")):
    """
    移除监听路径

    Args:
        path: 要移除的路径

    Returns:
        移除结果
    """
    service = get_pdf_watcher_service()
    service.remove_watch_path(path)

    return {"success": True, "message": f"已移除监听路径: {path}"}


@router.post("/watcher/rescan")
async def rescan_files(background_tasks: BackgroundTasks):
    """
    重新扫描所有监听路径

    Returns:
        扫描结果
    """
    service = get_pdf_watcher_service()
    background_tasks.add_task(service.rescan_all)

    return {"success": True, "message": "重新扫描已启动"}


@router.post("/start")
async def start_pdf_queue(
    background_tasks: BackgroundTasks
):
    """
    启动 PDF 解析队列（如果未运行）

    Returns:
        状态信息
    """
    manager = get_pdf_queue_manager()

    if manager._running:
        return {
            "status": "already_running",
            "message": "队列已在运行"
        }

    # 启动队列处理
    background_tasks.add_task(manager.start)

    return {
        "status": "started",
        "message": "队列已启动"
    }
