"""
工艺文件辅助编辑系统 - 对话管理器
管理用户与系统的对话历史、上下文和状态

支持两种模式：
1. 内存模式：纯内存操作，不持久化
2. Repository模式：底层使用Repository持久化
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
from dataclasses import dataclass, asdict

from app.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Interaction:
    """单次交互记录"""
    id: str
    timestamp: str
    user_input: str
    intent: Dict[str, Any]
    tasks: List[Dict[str, Any]]
    result: Dict[str, Any]
    state: str
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class DialogManager:
    """
    对话管理器

    管理用户与系统的对话历史，维护上下文信息，
    支持对话的持久化和检索。

    使用方式：
    ```python
    # 内存模式（向后兼容）
    dm = DialogManager()

    # Repository模式（推荐）
    from app.repositories import get_repository
    repo = get_repository()
    dm = DialogManager(repository=repo, task_id="电缆装配_20260224")
    ```
    """

    def __init__(
        self,
        max_history: int = 100,
        repository=None,
        task_id: Optional[str] = None,
    ):
        """
        初始化对话管理器

        Args:
            max_history: 最大历史记录数
            repository: TaskMemoryRepository实例（可选）
            task_id: 关联的任务ID（使用Repository时需要）
        """
        self.max_history = max_history
        self.repository = repository
        self.task_id = task_id

        # 内存缓存
        self.interactions: List[Interaction] = []
        self.current_context: Dict[str, Any] = {
            "session_start": datetime.now().isoformat(),
            "topic": None,
            "user_preferences": {},
            "system_state": {}
        }

        logger.info(
            "dialog_manager_initialized",
            max_history=max_history,
            has_repository=repository is not None,
            task_id=task_id,
        )

    async def add_interaction(
        self,
        user_input: str,
        intent: Dict[str, Any],
        tasks: List[Dict[str, Any]],
        result: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        添加交互记录

        Args:
            user_input: 用户输入
            intent: 识别出的意图
            tasks: 分解的任务列表
            result: 处理结果
            metadata: 附加元数据

        Returns:
            交互记录ID
        """
        interaction_id = f"interaction_{len(self.interactions)}_{datetime.now().timestamp()}"

        interaction = Interaction(
            id=interaction_id,
            timestamp=datetime.now().isoformat(),
            user_input=user_input,
            intent=intent,
            tasks=tasks,
            result=result,
            state=result.get("state", "unknown"),
            metadata=metadata or {}
        )

        # 添加到内存缓存
        self.interactions.append(interaction)

        # 限制内存历史记录数量
        if len(self.interactions) > self.max_history:
            self.interactions = self.interactions[-self.max_history:]

        # 持久化到Repository
        if self.repository and self.task_id:
            # 添加用户消息
            self.repository.add_message(
                task_id=self.task_id,
                role="user",
                content=user_input,
                metadata={
                    "intent": intent,
                    "interaction_id": interaction_id,
                }
            )

            # 添加助手回复
            result_content = result.get("result", {}).get("generated_content", "") or \
                            result.get("message", str(result))
            self.repository.add_message(
                task_id=self.task_id,
                role="assistant",
                content=result_content,
                metadata={
                    "tasks": tasks,
                    "state": result.get("state"),
                    "interaction_id": interaction_id,
                }
            )

        # 更新上下文
        await self._update_context(interaction)

        logger.info(
            "interaction_added",
            interaction_id=interaction_id,
            intent_type=intent.get("type"),
            task_count=len(tasks),
            result_state=result.get("state"),
            persisted=self.repository is not None,
        )

        return interaction_id

    async def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        添加单条消息（简化接口）

        Args:
            role: 角色 (user/assistant/system)
            content: 消息内容
            metadata: 元数据

        Returns:
            消息ID
        """
        message_id = f"msg_{datetime.now().strftime('%H%M%S')}_{len(self.interactions)}"

        # 持久化到Repository
        if self.repository and self.task_id:
            message_id = self.repository.add_message(
                task_id=self.task_id,
                role=role,
                content=content,
                metadata=metadata,
            )

        logger.info(
            "message_added",
            message_id=message_id,
            role=role,
            content_length=len(content),
        )

        return message_id

    async def _update_context(self, interaction: Interaction):
        """
        根据交互更新对话上下文

        Args:
            interaction: 交互记录
        """
        # 更新话题
        intent_type = interaction.intent.get("type")
        if intent_type:
            self.current_context["topic"] = intent_type

        # 更新用户偏好（基于历史交互）
        if "user_preferences" not in self.current_context:
            self.current_context["user_preferences"] = {}

        # 记录用户常用的术语或表达方式
        user_input = interaction.user_input.lower()
        if "prefer" in user_input or "like" in user_input:
            # 可以在这里提取用户偏好信息
            pass

        # 更新系统状态
        self.current_context["system_state"] = {
            "last_interaction_time": interaction.timestamp,
            "total_interactions": len(self.interactions),
            "current_topic": intent_type
        }

        logger.debug("context_updated", topic=intent_type)

    async def get_history(self, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """
        获取对话历史

        Args:
            limit: 返回的记录数
            offset: 偏移量

        Returns:
            交互记录列表
        """
        # 优先从Repository获取
        if self.repository and self.task_id:
            messages = self.repository.get_messages(
                task_id=self.task_id,
                limit=limit * 2,  # 用户+助手各一条
                offset=offset * 2,
            )
            # 转换为兼容格式
            history = []
            for i in range(0, len(messages) - 1, 2):
                if i + 1 < len(messages):
                    user_msg = messages[i]
                    assistant_msg = messages[i + 1]
                    history.append({
                        "id": user_msg.id,
                        "timestamp": user_msg.timestamp.isoformat() if hasattr(user_msg.timestamp, 'isoformat') else str(user_msg.timestamp),
                        "user_input": user_msg.content,
                        "result": {"message": assistant_msg.content},
                        "state": assistant_msg.metadata.get("state", "unknown") if assistant_msg.metadata else "unknown",
                    })
            return history

        # 从内存获取
        start = max(0, len(self.interactions) - limit - offset)
        end = len(self.interactions) - offset
        history = self.interactions[max(start, 0):end]

        # 转换为字典格式
        history_dicts = [interaction.to_dict() for interaction in history]

        logger.debug("history_retrieved", count=len(history_dicts), limit=limit, offset=offset)

        return history_dicts

    async def get_context(self) -> Dict[str, Any]:
        """
        获取当前对话上下文

        Returns:
            上下文信息
        """
        return self.current_context.copy()

    async def update_context(self, updates: Dict[str, Any]):
        """
        更新对话上下文

        Args:
            updates: 要更新的内容
        """
        self.current_context.update(updates)
        logger.debug("context_manually_updated", update_keys=list(updates.keys()))

    async def clear(self):
        """
        清空对话历史（保留当前会话）
        """
        self.interactions.clear()
        # 重置上下文但保留会话开始时间
        session_start = self.current_context.get("session_start")
        self.current_context = {
            "session_start": session_start or datetime.now().isoformat(),
            "topic": None,
            "user_preferences": {},
            "system_state": {}
        }

        logger.info("dialog_history_cleared")

    async def search_interactions(
        self,
        keyword: Optional[str] = None,
        intent_type: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        搜索交互记录

        Args:
            keyword: 关键词（在用户输入中搜索）
            intent_type: 意图类型
            state: 结果状态
            limit: 返回数量限制

        Returns:
            匹配的交互记录
        """
        results = []

        for interaction in reversed(self.interactions):  # 从最新开始搜索
            match = True

            # 关键词搜索
            if keyword and keyword.lower() not in interaction.user_input.lower():
                match = False

            # 意图类型过滤
            if intent_type and interaction.intent.get("type") != intent_type:
                match = False

            # 状态过滤
            if state and interaction.state != state:
                match = False

            if match:
                results.append(interaction.to_dict())

            if len(results) >= limit:
                break

        logger.debug(
            "interactions_searched",
            keyword=keyword,
            intent_type=intent_type,
            state=state,
            result_count=len(results)
        )

        return results

    async def get_statistics(self) -> Dict[str, Any]:
        """
        获取对话统计信息

        Returns:
            统计信息
        """
        if not self.interactions:
            return {
                "total_interactions": 0,
                "first_interaction": None,
                "last_interaction": None,
                "intent_distribution": {},
                "state_distribution": {}
            }

        # 计算意图分布
        intent_distribution = {}
        state_distribution = {}

        for interaction in self.interactions:
            intent_type = interaction.intent.get("type", "unknown")
            intent_distribution[intent_type] = intent_distribution.get(intent_type, 0) + 1

            state = interaction.state
            state_distribution[state] = state_distribution.get(state, 0) + 1

        stats = {
            "total_interactions": len(self.interactions),
            "first_interaction": self.interactions[0].timestamp if self.interactions else None,
            "last_interaction": self.interactions[-1].timestamp if self.interactions else None,
            "intent_distribution": intent_distribution,
            "state_distribution": state_distribution,
            "session_duration": self._calculate_session_duration()
        }

        logger.debug("statistics_calculated", total_interactions=len(self.interactions))

        return stats

    def _calculate_session_duration(self) -> Optional[str]:
        """
        计算会话持续时间

        Returns:
            持续时间字符串，或None
        """
        if not self.interactions:
            return None

        session_start = self.current_context.get("session_start")
        if not session_start:
            return None

        try:
            start_time = datetime.fromisoformat(session_start)
            end_time = datetime.now()
            duration = end_time - start_time

            # 格式化为可读字符串
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)

            if hours > 0:
                return f"{int(hours)}小时{int(minutes)}分钟"
            elif minutes > 0:
                return f"{int(minutes)}分钟{int(seconds)}秒"
            else:
                return f"{int(seconds)}秒"

        except (ValueError, TypeError):
            return None

    async def export_history(self, format: str = "json") -> str:
        """
        导出对话历史

        Args:
            format: 导出格式（目前只支持json）

        Returns:
            导出的数据
        """
        if format.lower() != "json":
            raise ValueError(f"不支持的导出格式: {format}")

        export_data = {
            "export_time": datetime.now().isoformat(),
            "total_interactions": len(self.interactions),
            "session_context": self.current_context,
            "interactions": [interaction.to_dict() for interaction in self.interactions]
        }

        logger.info("history_exported", format=format, interaction_count=len(self.interactions))

        return json.dumps(export_data, ensure_ascii=False, indent=2)

    def set_task(self, task_id: str):
        """
        设置关联的任务ID

        Args:
            task_id: 任务ID
        """
        self.task_id = task_id
        logger.info("dialog_manager_task_set", task_id=task_id)
