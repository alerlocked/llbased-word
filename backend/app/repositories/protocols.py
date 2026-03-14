"""
Repository接口协议
定义任务记忆存储的抽象接口，支持JSON/SQLite等多种实现
"""
from typing import Protocol, List, Dict, Any, Optional, runtime_checkable
from datetime import datetime

from app.models.task_memory import (
    TaskMeta,
    TaskState,
    Message,
    Conversation,
    Decision,
    DecisionLog,
    TaskContext,
    TaskStatus,
    ProcessState,
)


@runtime_checkable
class TaskMemoryRepository(Protocol):
    """
    任务记忆存储接口协议

    定义所有任务记忆操作的抽象接口，支持多种存储后端实现：
    - JsonFileRepository: JSON文件存储，用于单机调试
    - SQLiteRepository: SQLite数据库存储，用于部署环境
    """

    def create_task(
        self,
        task_name: str,
        task_type: str = "craft_document_edit",
        source_docs: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        创建新任务

        Args:
            task_name: 任务名称
            task_type: 任务类型
            source_docs: 关联的源文档列表
            tags: 标签列表
            metadata: 额外元数据

        Returns:
            task_id: 任务ID，格式为 {task_name}_{timestamp}
        """
        ...

    def get_meta(self, task_id: str) -> Optional[TaskMeta]:
        """
        获取任务元数据

        Args:
            task_id: 任务ID

        Returns:
            TaskMeta或None（任务不存在时）
        """
        ...

    def update_meta(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新任务元数据

        Args:
            task_id: 任务ID
            updates: 要更新的字段

        Returns:
            是否更新成功
        """
        ...

    def get_state(self, task_id: str) -> Optional[TaskState]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            TaskState或None
        """
        ...

    def update_state(
        self,
        task_id: str,
        new_state: ProcessState,
        pending_action: Optional[Dict[str, Any]] = None,
        context_update: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        更新任务状态

        Args:
            task_id: 任务ID
            new_state: 新状态
            pending_action: 待执行动作
            context_update: 状态上下文更新

        Returns:
            是否更新成功
        """
        ...

    def get_messages(
        self,
        task_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Message]:
        """
        获取对话消息

        Args:
            task_id: 任务ID
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            消息列表
        """
        ...

    def add_message(
        self,
        task_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        添加对话消息

        Args:
            task_id: 任务ID
            role: 角色 (user/assistant/system)
            content: 消息内容
            metadata: 元数据

        Returns:
            消息ID
        """
        ...

    def get_decisions(self, task_id: str) -> List[Decision]:
        """
        获取决策记录

        Args:
            task_id: 任务ID

        Returns:
            决策列表
        """
        ...

    def add_decision(
        self,
        task_id: str,
        decision_type: str,
        context: str,
        options: List[str],
        selected: str,
        reason: str = "",
        user_confirmed: bool = False,
        source: str = "agent_suggestion",
    ) -> str:
        """
        添加决策记录

        Args:
            task_id: 任务ID
            decision_type: 决策类型
            context: 决策上下文
            options: 可选方案
            selected: 选择的方案
            reason: 选择原因
            user_confirmed: 是否经用户确认
            source: 决策来源

        Returns:
            决策ID
        """
        ...

    def get_context(self, task_id: str) -> str:
        """
        构建并获取任务的完整上下文

        包括：任务元信息、当前状态、对话历史、决策记录

        Args:
            task_id: 任务ID

        Returns:
            格式化的上下文字符串（Markdown格式）
        """
        ...

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TaskMeta]:
        """
        列出任务

        Args:
            status: 按状态过滤（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            任务元数据列表
        """
        ...

    def delete_task(self, task_id: str) -> bool:
        """
        删除任务

        Args:
            task_id: 任务ID

        Returns:
            是否删除成功
        """
        ...

    def task_exists(self, task_id: str) -> bool:
        """
        检查任务是否存在

        Args:
            task_id: 任务ID

        Returns:
            是否存在
        """
        ...

    def get_artifacts_dir(self, task_id: str) -> Optional[str]:
        """
        获取任务的artifacts目录路径

        Args:
            task_id: 任务ID

        Returns:
            目录路径或None
        """
        ...
