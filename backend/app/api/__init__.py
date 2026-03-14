"""
API路由包
"""
from .task import router as task_router
from .document import router as document_router

__all__ = [
    "task_router",
    "document_router",
]
