"""
PDF解析队列管理器

功能：
1. 并发控制 - 限制同时解析的PDF数量（默认最大2个）
2. 增量解析 - 基于文件哈希避免重复解析
3. 队列管理 - 支持任务优先级和状态跟踪
4. 输出管理 - 保持源文件夹结构，文件名与PDF一致
"""
import asyncio
import hashlib
import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field, asdict

from app.shared.logging import get_logger
from app.config import settings

logger = get_logger(__name__)


class PDFTaskStatus(str, Enum):
    """PDF解析任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PDFTaskPriority(int, Enum):
    """PDF解析任务优先级"""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    URGENT = 0


@dataclass
class PDFTask:
    """PDF解析任务"""
    task_id: str
    source_path: str
    output_path: str
    file_hash: str
    file_size: int
    status: PDFTaskStatus = PDFTaskStatus.PENDING
    priority: PDFTaskPriority = PDFTaskPriority.NORMAL
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    progress: int = 0  # 0-100
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "source_path": self.source_path,
            "output_path": self.output_path,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "progress": self.progress,
            "result": self.result
        }


@dataclass
class PDFQueueStats:
    """队列统计信息"""
    total_tasks: int = 0
    pending_tasks: int = 0
    processing_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    active_workers: int = 0
    max_workers: int = 2

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PDFQueueManager:
    """
    PDF解析队列管理器

    使用asyncio实现并发控制和队列管理
    """

    def __init__(
        self,
        max_concurrent: int = 2,
        output_base_path: Optional[str] = None,
        state_file: Optional[str] = None
    ):
        """
        初始化队列管理器

        Args:
            max_concurrent: 最大并发数（默认2）
            output_base_path: 输出基础路径（默认使用 settings.DATA_DIR）
            state_file: 状态持久化文件路径（默认使用 settings.DATA_DIR）
        """
        self.max_concurrent = max_concurrent
        # 使用统一的配置路径
        self.output_base_path = Path(output_base_path) if output_base_path else settings.DATA_DIR / "parsed_pdfs"
        self.state_file = Path(state_file) if state_file else settings.DATA_DIR / "pdf_queue_state.json"

        # 并发控制信号量
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # 任务存储
        self._tasks: Dict[str, PDFTask] = {}  # task_id -> PDFTask
        self._file_hash_index: Dict[str, str] = {}  # file_hash -> task_id
        self._source_path_index: Dict[str, str] = {}  # source_path -> task_id

        # 任务队列（按优先级排序）
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()

        # 处理中的任务
        self._processing: Dict[str, asyncio.Task] = {}

        # 解析器函数
        self._parser_func: Optional[Callable[[PDFTask], Awaitable[Dict[str, Any]]]] = None

        # 运行状态
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

        # 统计信息
        self._stats = PDFQueueStats(max_workers=max_concurrent)

        # 加载持久化状态
        self._load_state()

        logger.info(
            "pdf_queue_manager_initialized",
            max_concurrent=max_concurrent,
            output_base_path=str(self.output_base_path),
            loaded_tasks=len(self._tasks)
        )

    def set_parser(self, parser_func: Callable[[PDFTask], Awaitable[Dict[str, Any]]]):
        """
        设置PDF解析函数

        Args:
            parser_func: 异步解析函数，接收PDFTask，返回解析结果
        """
        self._parser_func = parser_func
        logger.info("pdf_parser_set", parser_name=parser_func.__name__ if hasattr(parser_func, '__name__') else 'custom')

    async def start(self):
        """启动队列处理"""
        if self._running:
            logger.warning("pdf_queue_already_running")
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())
        logger.info("pdf_queue_started")

    async def stop(self):
        """停止队列处理"""
        self._running = False

        # 取消所有处理中的任务
        for task_id, task in self._processing.items():
            task.cancel()
            if task_id in self._tasks:
                self._tasks[task_id].status = PDFTaskStatus.CANCELLED

        # 等待工作线程结束
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        # 保存状态
        self._save_state()
        logger.info("pdf_queue_stopped")

    async def add_task(
        self,
        source_path: str,
        output_path: Optional[str] = None,
        priority: PDFTaskPriority = PDFTaskPriority.NORMAL,
        force_reparse: bool = False
    ) -> Optional[str]:
        """
        添加PDF解析任务

        Args:
            source_path: PDF源文件路径
            output_path: 输出路径（可选，默认自动生成）
            priority: 任务优先级
            force_reparse: 是否强制重新解析（忽略哈希检查）

        Returns:
            任务ID，如果文件已存在且未强制重解析则返回None
        """
        source_path_obj = Path(source_path)

        # 验证文件存在
        if not source_path_obj.exists():
            logger.error("pdf_file_not_found", source_path=source_path)
            return None

        # 计算文件哈希
        file_hash = await self._calculate_file_hash(source_path_obj)
        file_size = source_path_obj.stat().st_size

        # 生成或使用提供的输出路径
        if output_path:
            final_output_path = Path(output_path)
        else:
            final_output_path = self._get_output_path(source_path_obj)

        # 检查是否已存在相同文件（增量解析）
        if not force_reparse:
            if file_hash in self._file_hash_index:
                existing_task_id = self._file_hash_index[file_hash]
                existing_task = self._tasks.get(existing_task_id)
                if existing_task and existing_task.status == PDFTaskStatus.COMPLETED:
                    logger.info(
                        "pdf_already_parsed",
                        source_path=source_path,
                        task_id=existing_task_id
                    )
                    return None  # 已解析，跳过

        # 检查是否已有相同路径的任务
        if source_path in self._source_path_index:
            existing_task_id = self._source_path_index[source_path]
            existing_task = self._tasks.get(existing_task_id)
            if existing_task and existing_task.status in [
                PDFTaskStatus.PENDING,
                PDFTaskStatus.QUEUED,
                PDFTaskStatus.PROCESSING
            ]:
                logger.info(
                    "pdf_task_already_exists",
                    source_path=source_path,
                    task_id=existing_task_id,
                    status=existing_task.status.value
                )
                return existing_task_id

        # 生成任务ID和输出路径
        task_id = self._generate_task_id(source_path_obj)

        # 创建任务
        task = PDFTask(
            task_id=task_id,
            source_path=str(source_path_obj),
            output_path=str(final_output_path),
            file_hash=file_hash,
            file_size=file_size,
            status=PDFTaskStatus.PENDING,
            priority=priority
        )

        # 存储任务
        self._tasks[task_id] = task
        self._file_hash_index[file_hash] = task_id
        self._source_path_index[str(source_path_obj)] = task_id

        # 添加到队列
        await self._queue.put((priority.value, task_id))
        task.status = PDFTaskStatus.QUEUED

        # 更新统计
        self._stats.total_tasks += 1
        self._stats.pending_tasks += 1

        logger.info(
            "pdf_task_added",
            task_id=task_id,
            source_path=source_path,
            file_size=file_size,
            priority=priority.name
        )

        # 保存状态
        self._save_state()

        return task_id

    async def add_tasks_batch(
        self,
        source_paths: List[str],
        priority: PDFTaskPriority = PDFTaskPriority.NORMAL
    ) -> List[str]:
        """
        批量添加PDF解析任务

        Args:
            source_paths: PDF源文件路径列表
            priority: 任务优先级

        Returns:
            添加成功的任务ID列表
        """
        added_task_ids = []

        for source_path in source_paths:
            task_id = await self.add_task(source_path, priority)
            if task_id:
                added_task_ids.append(task_id)

        logger.info(
            "pdf_batch_tasks_added",
            total_files=len(source_paths),
            added_tasks=len(added_task_ids),
            skipped=len(source_paths) - len(added_task_ids)
        )

        return added_task_ids

    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]

        # 如果任务正在处理中
        if task_id in self._processing:
            self._processing[task_id].cancel()
            task.status = PDFTaskStatus.CANCELLED
            self._stats.processing_tasks -= 1
            logger.info("pdf_task_cancelled", task_id=task_id, was_processing=True)
        elif task.status in [PDFTaskStatus.PENDING, PDFTaskStatus.QUEUED]:
            task.status = PDFTaskStatus.CANCELLED
            self._stats.pending_tasks -= 1
            logger.info("pdf_task_cancelled", task_id=task_id, was_processing=False)

        self._save_state()
        return True

    def get_task(self, task_id: str) -> Optional[PDFTask]:
        """获取任务信息"""
        return self._tasks.get(task_id)

    def get_task_by_path(self, source_path: str) -> Optional[PDFTask]:
        """通过源路径获取任务"""
        task_id = self._source_path_index.get(source_path)
        if task_id:
            return self._tasks.get(task_id)
        return None

    def get_all_tasks(self, status: Optional[PDFTaskStatus] = None) -> List[PDFTask]:
        """
        获取所有任务

        Args:
            status: 过滤状态（可选）

        Returns:
            任务列表
        """
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def get_stats(self) -> PDFQueueStats:
        """获取队列统计信息"""
        self._stats.pending_tasks = sum(
            1 for t in self._tasks.values()
            if t.status in [PDFTaskStatus.PENDING, PDFTaskStatus.QUEUED]
        )
        self._stats.processing_tasks = sum(
            1 for t in self._tasks.values()
            if t.status == PDFTaskStatus.PROCESSING
        )
        self._stats.completed_tasks = sum(
            1 for t in self._tasks.values()
            if t.status == PDFTaskStatus.COMPLETED
        )
        self._stats.failed_tasks = sum(
            1 for t in self._tasks.values()
            if t.status == PDFTaskStatus.FAILED
        )
        self._stats.active_workers = len(self._processing)
        return self._stats

    async def _process_queue(self):
        """队列处理循环"""
        logger.info("pdf_queue_processor_started")

        while self._running:
            try:
                # 从队列获取任务
                try:
                    priority, task_id = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # 获取任务
                task = self._tasks.get(task_id)
                if not task or task.status == PDFTaskStatus.CANCELLED:
                    continue

                # 使用信号量控制并发
                async with self._semaphore:
                    await self._process_single_task(task)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("pdf_queue_processor_error", error=str(e))
                await asyncio.sleep(1)

        logger.info("pdf_queue_processor_stopped")

    async def _process_single_task(self, task: PDFTask):
        """
        处理单个PDF任务

        Args:
            task: PDF任务
        """
        task.status = PDFTaskStatus.PROCESSING
        task.started_at = datetime.now().isoformat()
        task.progress = 0

        logger.info(
            "pdf_task_processing_started",
            task_id=task.task_id,
            source_path=task.source_path
        )

        try:
            # 检查解析器是否设置
            if not self._parser_func:
                raise ValueError("PDF解析器未设置，请调用 set_parser() 方法")

            # 确保输出目录存在
            output_path = Path(task.output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 执行解析
            task.progress = 10
            result = await self._parser_func(task)

            # 更新任务状态
            task.status = PDFTaskStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
            task.progress = 100
            task.result = result

            self._stats.completed_tasks += 1
            self._stats.processing_tasks -= 1

            logger.info(
                "pdf_task_completed",
                task_id=task.task_id,
                source_path=task.source_path,
                output_path=task.output_path
            )

        except asyncio.CancelledError:
            task.status = PDFTaskStatus.CANCELLED
            task.error_message = "任务被取消"
            logger.info("pdf_task_cancelled_during_processing", task_id=task.task_id)

        except Exception as e:
            task.status = PDFTaskStatus.FAILED
            task.completed_at = datetime.now().isoformat()
            task.error_message = str(e)

            self._stats.failed_tasks += 1
            self._stats.processing_tasks -= 1

            logger.error(
                "pdf_task_failed",
                task_id=task.task_id,
                source_path=task.source_path,
                error=str(e)
            )

        finally:
            # 从处理中移除
            if task.task_id in self._processing:
                del self._processing[task.task_id]

            # 保存状态
            self._save_state()

    async def _calculate_file_hash(self, file_path: Path) -> str:
        """
        计算文件哈希值

        Args:
            file_path: 文件路径

        Returns:
            MD5哈希值
        """
        hash_md5 = hashlib.md5()
        loop = asyncio.get_event_loop()

        def read_chunks():
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()

        return await loop.run_in_executor(None, read_chunks)

    def _generate_task_id(self, source_path: Path) -> str:
        """
        生成任务ID

        Args:
            source_path: 源文件路径

        Returns:
            任务ID（基于文件路径的稳定ID）
        """
        # 使用文件路径的哈希作为稳定ID
        path_hash = hashlib.md5(str(source_path).encode()).hexdigest()[:12]
        return f"pdf_{path_hash}"

    def _get_output_path(self, source_path: Path) -> Path:
        """
        获取输出路径

        保持源文件夹结构，文件名与PDF一致（不加时间戳）

        Args:
            source_path: 源文件路径

        Returns:
            输出HTML文件路径
        """
        # 获取相对路径（如果源文件在base_path下）
        # 否则使用绝对路径结构
        relative_path = source_path.stem  # 不含扩展名的文件名

        # 输出为HTML文件
        output_path = self.output_base_path / f"{relative_path}.html"

        return output_path

    def _load_state(self):
        """加载持久化状态"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)

                # 恢复任务
                for task_data in state.get('tasks', []):
                    task = PDFTask(
                        task_id=task_data['task_id'],
                        source_path=task_data['source_path'],
                        output_path=task_data['output_path'],
                        file_hash=task_data['file_hash'],
                        file_size=task_data['file_size'],
                        status=PDFTaskStatus(task_data['status']),
                        priority=PDFTaskPriority(task_data['priority']),
                        created_at=task_data['created_at'],
                        started_at=task_data.get('started_at'),
                        completed_at=task_data.get('completed_at'),
                        error_message=task_data.get('error_message'),
                        progress=task_data.get('progress', 0),
                        result=task_data.get('result')
                    )

                    self._tasks[task.task_id] = task
                    self._file_hash_index[task.file_hash] = task.task_id
                    self._source_path_index[task.source_path] = task.task_id

                logger.info("pdf_queue_state_loaded", tasks_count=len(self._tasks))

        except Exception as e:
            logger.error("pdf_queue_state_load_failed", error=str(e))

    def _save_state(self):
        """保存持久化状态"""
        try:
            # 确保目录存在
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            state = {
                'tasks': [task.to_dict() for task in self._tasks.values()],
                'saved_at': datetime.now().isoformat()
            }

            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error("pdf_queue_state_save_failed", error=str(e))

    def clear_completed_tasks(self, older_than_hours: int = 24):
        """
        清理已完成的任务

        Args:
            older_than_hours: 清理多少小时前的任务
        """
        cutoff = datetime.now()
        to_remove = []

        for task_id, task in self._tasks.items():
            if task.status == PDFTaskStatus.COMPLETED:
                if task.completed_at:
                    completed_time = datetime.fromisoformat(task.completed_at)
                    hours_diff = (cutoff - completed_time).total_seconds() / 3600
                    if hours_diff > older_than_hours:
                        to_remove.append(task_id)

        for task_id in to_remove:
            task = self._tasks[task_id]
            del self._tasks[task_id]
            if task.file_hash in self._file_hash_index:
                del self._file_hash_index[task.file_hash]
            if task.source_path in self._source_path_index:
                del self._source_path_index[task.source_path]

        if to_remove:
            logger.info("pdf_queue_cleaned", removed_count=len(to_remove))
            self._save_state()


# 全局队列管理器实例
_pdf_queue_manager: Optional[PDFQueueManager] = None


def get_pdf_queue_manager() -> PDFQueueManager:
    """获取全局PDF队列管理器实例"""
    global _pdf_queue_manager
    if _pdf_queue_manager is None:
        _pdf_queue_manager = PDFQueueManager()
    return _pdf_queue_manager
