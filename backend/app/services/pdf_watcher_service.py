"""
PDF文件监听服务

功能：
1. 监听指定文件夹的PDF文件变化
2. 自动将新增/修改的PDF加入解析队列
3. 支持增量解析（避免重复解析）
4. 可配置监听路径和过滤规则
"""
import asyncio
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from app.shared.logging import get_logger
from app.services.pdf_queue_manager import (
    get_pdf_queue_manager,
    PDFQueueManager,
    PDFTaskPriority
)

logger = get_logger(__name__)


class PDFFileEventHandler(FileSystemEventHandler):
    """PDF文件事件处理器"""

    def __init__(
        self,
        callback,
        watched_extensions: List[str] = None,
        ignore_patterns: List[str] = None
    ):
        self.callback = callback
        self.watched_extensions = watched_extensions or ['.pdf']
        self.ignore_patterns = ignore_patterns or [
            '.tmp', '.temp', '~', '.crdownload', '.download'
        ]
        self._processing_files: Set[str] = set()

    def on_created(self, event):
        """文件创建事件"""
        if event.is_directory:
            return

        file_path = event.src_path
        if self._should_process(file_path):
            # 防止重复处理
            if file_path not in self._processing_files:
                self._processing_files.add(file_path)
                # 延迟处理，等待文件写入完成
                asyncio.create_task(self._delayed_process('created', file_path))

    def on_modified(self, event):
        """文件修改事件"""
        if event.is_directory:
            return

        file_path = event.src_path
        if self._should_process(file_path):
            if file_path not in self._processing_files:
                self._processing_files.add(file_path)
                asyncio.create_task(self._delayed_process('modified', file_path))

    def _should_process(self, file_path: str) -> bool:
        """判断是否应该处理该文件"""
        path = Path(file_path)

        # 检查扩展名
        if path.suffix.lower() not in self.watched_extensions:
            return False

        # 检查忽略模式
        filename = path.name.lower()
        for pattern in self.ignore_patterns:
            if pattern in filename:
                return False

        # 检查隐藏文件
        if filename.startswith('.'):
            return False

        return True

    async def _delayed_process(self, event_type: str, file_path: str):
        """延迟处理（等待文件写入完成）"""
        try:
            # 等待文件稳定
            await asyncio.sleep(2)

            # 检查文件是否仍然存在
            if not Path(file_path).exists():
                logger.debug("file_disappeared", file_path=file_path)
                return

            # 检查文件是否仍在写入
            if await self._is_file_still_writing(file_path):
                # 再等待一段时间
                await asyncio.sleep(3)
                if await self._is_file_still_writing(file_path):
                    logger.warning("file_still_writing", file_path=file_path)
                    return

            await self.callback(event_type, file_path)

        except Exception as e:
            logger.error("delayed_process_failed", file_path=file_path, error=str(e))
        finally:
            self._processing_files.discard(file_path)

    async def _is_file_still_writing(self, file_path: str) -> bool:
        """检查文件是否仍在写入"""
        try:
            path = Path(file_path)
            stat1 = path.stat()
            await asyncio.sleep(1)
            stat2 = path.stat()

            # 如果文件大小或修改时间变化，说明仍在写入
            return stat1.st_size != stat2.st_size or stat1.st_mtime != stat2.st_mtime

        except Exception:
            return False


class PDFWatcherService:
    """
    PDF文件监听服务

    监听指定目录的PDF文件变化，自动加入解析队列
    """

    def __init__(
        self,
        watch_paths: List[str] = None,
        queue_manager: PDFQueueManager = None,
        auto_start: bool = False
    ):
        """
        初始化监听服务

        Args:
            watch_paths: 监听路径列表
            queue_manager: PDF队列管理器
            auto_start: 是否自动开始监听
        """
        self.watch_paths = [Path(p) for p in (watch_paths or [])]
        self.queue_manager = queue_manager or get_pdf_queue_manager()

        self._observer: Optional[Observer] = None
        self._is_running = False
        self._scanned_files: Dict[str, str] = {}  # path -> file_hash

        # 配置
        self.recursive = True
        self.scan_on_start = True
        self.default_priority = PDFTaskPriority.NORMAL

        if auto_start:
            asyncio.create_task(self.start())

        logger.info(
            "pdf_watcher_service_initialized",
            watch_paths=[str(p) for p in self.watch_paths]
        )

    def add_watch_path(self, path: str):
        """
        添加监听路径

        Args:
            path: 监听路径
        """
        path_obj = Path(path)
        if path_obj not in self.watch_paths:
            self.watch_paths.append(path_obj)
            logger.info("watch_path_added", path=path)

            # 如果正在运行，为新路径设置监听
            if self._is_running and self._observer:
                event_handler = PDFFileEventHandler(self._handle_file_event)
                self._observer.schedule(event_handler, path, recursive=self.recursive)

                # 扫描现有文件
                asyncio.create_task(self._scan_path(path_obj))

    def remove_watch_path(self, path: str):
        """
        移除监听路径

        Args:
            path: 监听路径
        """
        path_obj = Path(path)
        if path_obj in self.watch_paths:
            self.watch_paths.remove(path_obj)
            logger.info("watch_path_removed", path=path)

    async def start(self):
        """开始监听"""
        if self._is_running:
            logger.warning("pdf_watcher_already_running")
            return

        try:
            # 确保队列管理器已启动
            await self.queue_manager.start()

            # 创建文件系统监听器
            self._observer = Observer()
            event_handler = PDFFileEventHandler(self._handle_file_event)

            # 为每个路径设置监听
            for watch_path in self.watch_paths:
                if watch_path.exists():
                    self._observer.schedule(
                        event_handler,
                        str(watch_path),
                        recursive=self.recursive
                    )
                else:
                    logger.warning("watch_path_not_exists", path=str(watch_path))

            self._observer.start()
            self._is_running = True

            logger.info(
                "pdf_watcher_started",
                watch_paths=[str(p) for p in self.watch_paths]
            )

            # 扫描现有文件
            if self.scan_on_start:
                await self._scan_existing_files()

        except Exception as e:
            logger.error("pdf_watcher_start_failed", error=str(e))
            await self.stop()
            raise

    async def stop(self):
        """停止监听"""
        if not self._is_running:
            return

        try:
            if self._observer:
                self._observer.stop()
                self._observer.join(timeout=5)
                self._observer = None

            self._is_running = False

            # 停止队列管理器
            await self.queue_manager.stop()

            logger.info("pdf_watcher_stopped")

        except Exception as e:
            logger.error("pdf_watcher_stop_failed", error=str(e))

    async def _handle_file_event(self, event_type: str, file_path: str):
        """
        处理文件事件

        Args:
            event_type: 事件类型 (created/modified)
            file_path: 文件路径
        """
        logger.info(
            "pdf_file_event",
            event_type=event_type,
            file_path=file_path
        )

        try:
            # 检查文件哈希，避免重复处理
            file_hash = await self._calculate_file_hash(file_path)

            if file_path in self._scanned_files:
                if self._scanned_files[file_path] == file_hash:
                    # 文件未变化
                    logger.debug("pdf_file_unchanged", file_path=file_path)
                    return

            # 更新扫描记录
            self._scanned_files[file_path] = file_hash

            # 添加到队列（强制重解析如果是修改事件）
            force_reparse = (event_type == 'modified')
            task_id = await self.queue_manager.add_task(
                source_path=file_path,
                priority=self.default_priority,
                force_reparse=force_reparse
            )

            if task_id:
                logger.info(
                    "pdf_added_to_queue",
                    file_path=file_path,
                    task_id=task_id,
                    event_type=event_type
                )

        except Exception as e:
            logger.error(
                "pdf_file_event_handling_failed",
                file_path=file_path,
                error=str(e)
            )

    async def _scan_existing_files(self):
        """扫描现有文件"""
        logger.info("scanning_existing_pdf_files")

        total_scanned = 0
        total_added = 0

        for watch_path in self.watch_paths:
            if watch_path.exists():
                added = await self._scan_path(watch_path)
                total_scanned += added['scanned']
                total_added += added['added']

        logger.info(
            "pdf_scan_completed",
            total_scanned=total_scanned,
            total_added=total_added
        )

    async def _scan_path(self, path: Path) -> Dict[str, int]:
        """
        扫描指定路径

        Args:
            path: 扫描路径

        Returns:
            扫描统计
        """
        scanned = 0
        added = 0

        try:
            pattern = '*.pdf'
            if self.recursive:
                files = list(path.rglob(pattern))
            else:
                files = list(path.glob(pattern))

            for file_path in files:
                if file_path.is_file() and not file_path.name.startswith('.'):
                    scanned += 1

                    # 计算哈希
                    file_hash = await self._calculate_file_hash(str(file_path))
                    str_path = str(file_path)

                    # 检查是否已扫描
                    if str_path in self._scanned_files:
                        if self._scanned_files[str_path] == file_hash:
                            continue

                    # 更新扫描记录
                    self._scanned_files[str_path] = file_hash

                    # 添加到队列
                    task_id = await self.queue_manager.add_task(
                        source_path=str_path,
                        priority=self.default_priority,
                        force_reparse=False
                    )

                    if task_id:
                        added += 1

        except Exception as e:
            logger.error("path_scan_failed", path=str(path), error=str(e))

        return {'scanned': scanned, 'added': added}

    async def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希"""
        hash_md5 = hashlib.md5()
        loop = asyncio.get_event_loop()

        def read_chunks():
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()

        return await loop.run_in_executor(None, read_chunks)

    def get_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        return {
            "is_running": self._is_running,
            "watch_paths": [str(p) for p in self.watch_paths],
            "scanned_files_count": len(self._scanned_files),
            "queue_stats": self.queue_manager.get_stats().to_dict()
        }

    async def rescan_all(self):
        """重新扫描所有路径"""
        logger.info("rescanning_all_paths")
        await self._scan_existing_files()


# 全局监听服务实例
_pdf_watcher_service: Optional[PDFWatcherService] = None


def get_pdf_watcher_service() -> PDFWatcherService:
    """获取全局PDF监听服务实例"""
    global _pdf_watcher_service
    if _pdf_watcher_service is None:
        _pdf_watcher_service = PDFWatcherService()
    return _pdf_watcher_service


async def initialize_pdf_watcher(
    watch_paths: List[str] = None,
    max_concurrent: int = 2,
    output_base_path: str = "./data/parsed_pdfs"
) -> PDFWatcherService:
    """
    初始化PDF监听服务

    Args:
        watch_paths: 监听路径列表
        max_concurrent: 最大并发解析数
        output_base_path: 输出基础路径

    Returns:
        PDFWatcherService实例
    """
    global _pdf_watcher_service, _pdf_queue_manager

    from app.services.pdf_queue_manager import PDFQueueManager

    # 创建队列管理器
    queue_manager = PDFQueueManager(
        max_concurrent=max_concurrent,
        output_base_path=output_base_path
    )

    # 创建监听服务
    _pdf_watcher_service = PDFWatcherService(
        watch_paths=watch_paths,
        queue_manager=queue_manager
    )

    return _pdf_watcher_service
