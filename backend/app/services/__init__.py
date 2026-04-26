"""
服务模块包

包含以下服务：
- pdf_queue_manager: PDF解析队列管理器（并发控制、增量解析）
- pdf_watcher_service: PDF文件监听服务
- context_manager: 上下文管理
- context_builder: 上下文构建
- file_system_service: 文件系统服务
- memory_service: 记忆管理服务
"""

from app.services.pdf_queue_manager import (
    PDFQueueManager,
    PDFTask,
    PDFTaskStatus,
    PDFTaskPriority,
    get_pdf_queue_manager
)

from app.services.pdf_watcher_service import (
    PDFWatcherService,
    get_pdf_watcher_service,
    initialize_pdf_watcher
)

from app.services.memory_service import MemoryService

__all__ = [
    # PDF队列管理
    'PDFQueueManager',
    'PDFTask',
    'PDFTaskStatus',
    'PDFTaskPriority',
    'get_pdf_queue_manager',

    # PDF监听服务
    'PDFWatcherService',
    'get_pdf_watcher_service',
    'initialize_pdf_watcher',

    # 记忆管理
    'MemoryService',
]
