"""
JsonFileRepository - 基于JSON文件的任务记忆存储实现
用于单机调试，零依赖，可直接查看和调试
"""
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.shared.logging import get_logger
from app.models.task_memory import (
    TaskMeta,
    TaskState,
    TaskStatus,
    TaskContext,
    Message,
    MessageRole,
    Conversation,
    Decision,
    DecisionLog,
    DecisionType,
    ProcessState,
    StateTransition,
)

logger = get_logger(__name__)


class JsonFileRepository:
    """
    基于JSON文件的任务记忆存储

    目录结构:
    data/tasks/
    ├── 电缆装配编辑_20260224_143000/
    │   ├── meta.json
    │   ├── state.json
    │   ├── conversation.json
    │   ├── decisions.json
    │   └── artifacts/
    └── ...
    """

    META_FILE = "meta.json"
    STATE_FILE = "state.json"
    CONVERSATION_FILE = "conversation.json"
    DECISIONS_FILE = "decisions.json"
    ARTIFACTS_DIR = "artifacts"

    def __init__(self, base_dir: str = "data/tasks"):
        """
        初始化Repository

        Args:
            base_dir: 任务数据存储根目录
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info("json_repository_initialized", base_dir=str(self.base_dir))

    def _generate_task_id(self, task_name: str) -> str:
        """
        生成任务ID

        格式: {task_name}_{YYYYMMDD_HHMMSS}
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 清理任务名中的特殊字符
        safe_name = "".join(c for c in task_name if c.isalnum() or c in "._-").strip()
        return f"{safe_name}_{timestamp}"

    def _get_task_dir(self, task_id: str) -> Path:
        """获取任务目录路径"""
        return self.base_dir / task_id

    def _read_json(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """读取JSON文件"""
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error("json_read_failed", file=str(file_path), error=str(e))
            return None

    def _write_json(self, file_path: Path, data: Dict[str, Any]) -> bool:
        """写入JSON文件"""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=self._json_serializer)
            return True
        except IOError as e:
            logger.error("json_write_failed", file=str(file_path), error=str(e))
            return False

    def _json_serializer(self, obj):
        """JSON序列化器，处理datetime等类型"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "value"):  # Enum类型
            return obj.value
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def create_task(
        self,
        task_name: str,
        task_type: str = "craft_document_edit",
        source_docs: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建新任务"""
        task_id = self._generate_task_id(task_name)
        task_dir = self._get_task_dir(task_id)

        # 创建任务目录
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / self.ARTIFACTS_DIR).mkdir(exist_ok=True)

        now = datetime.now()

        # 创建meta.json
        meta = TaskMeta(
            task_id=task_id,
            task_name=task_name,
            task_type=task_type,
            created_at=now,
            updated_at=now,
            status=TaskStatus.PENDING,
            source_documents=source_docs or [],
            tags=tags or [],
            metadata=metadata or {},
        )
        self._write_json(task_dir / self.META_FILE, meta.model_dump())

        # 创建state.json
        state = TaskState(
            current_state=ProcessState.IDLE,
            state_history=[],
            pending_action=None,
            context={},
        )
        self._write_json(task_dir / self.STATE_FILE, state.model_dump())

        # 创建空的conversation.json
        conversation = Conversation(messages=[], summary=None)
        self._write_json(task_dir / self.CONVERSATION_FILE, conversation.model_dump())

        # 创建空的decisions.json
        decisions = DecisionLog(decisions=[])
        self._write_json(task_dir / self.DECISIONS_FILE, decisions.model_dump())

        logger.info(
            "task_created",
            task_id=task_id,
            task_name=task_name,
            task_type=task_type,
        )

        return task_id

    def get_meta(self, task_id: str) -> Optional[TaskMeta]:
        """获取任务元数据"""
        task_dir = self._get_task_dir(task_id)
        data = self._read_json(task_dir / self.META_FILE)
        if data:
            return TaskMeta(**data)
        return None

    def update_meta(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """更新任务元数据"""
        meta = self.get_meta(task_id)
        if not meta:
            logger.warning("task_not_found", task_id=task_id)
            return False

        # 更新字段
        for key, value in updates.items():
            if hasattr(meta, key):
                setattr(meta, key, value)

        meta.updated_at = datetime.now()

        task_dir = self._get_task_dir(task_id)
        success = self._write_json(task_dir / self.META_FILE, meta.model_dump())

        if success:
            logger.info("meta_updated", task_id=task_id, updated_fields=list(updates.keys()))

        return success

    def get_state(self, task_id: str) -> Optional[TaskState]:
        """获取任务状态"""
        task_dir = self._get_task_dir(task_id)
        data = self._read_json(task_dir / self.STATE_FILE)
        if data:
            return TaskState(**data)
        return None

    def update_state(
        self,
        task_id: str,
        new_state: ProcessState,
        pending_action: Optional[Dict[str, Any]] = None,
        context_update: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """更新任务状态"""
        state = self.get_state(task_id)
        if not state:
            logger.warning("task_state_not_found", task_id=task_id)
            return False

        old_state = state.current_state

        # 记录状态转换
        transition = StateTransition(
            from_state=old_state.value if isinstance(old_state, ProcessState) else old_state,
            to_state=new_state.value if isinstance(new_state, ProcessState) else new_state,
            timestamp=datetime.now(),
            trigger=None,
        )
        state.state_history.append(transition)

        # 更新状态
        state.current_state = new_state
        if pending_action is not None:
            state.pending_action = pending_action
        if context_update:
            state.context.update(context_update)

        task_dir = self._get_task_dir(task_id)
        success = self._write_json(task_dir / self.STATE_FILE, state.model_dump())

        if success:
            logger.info(
                "state_updated",
                task_id=task_id,
                from_state=old_state.value if hasattr(old_state, "value") else old_state,
                to_state=new_state.value if hasattr(new_state, "value") else new_state,
            )

        return success

    def get_messages(
        self,
        task_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Message]:
        """获取对话消息"""
        task_dir = self._get_task_dir(task_id)
        data = self._read_json(task_dir / self.CONVERSATION_FILE)
        if not data:
            return []

        conversation = Conversation(**data)
        messages = conversation.messages

        # 应用offset和limit
        start = min(offset, len(messages))
        end = min(offset + limit, len(messages))

        return messages[start:end]

    def add_message(
        self,
        task_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """添加对话消息"""
        task_dir = self._get_task_dir(task_id)

        # 读取现有对话
        data = self._read_json(task_dir / self.CONVERSATION_FILE)
        if data:
            conversation = Conversation(**data)
        else:
            conversation = Conversation(messages=[], summary=None)

        # 创建新消息
        message_id = f"msg_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%H%M%S')}"
        message = Message(
            id=message_id,
            role=MessageRole(role),
            content=content,
            timestamp=datetime.now(),
            metadata=metadata,
        )

        conversation.messages.append(message)

        # 保存
        self._write_json(task_dir / self.CONVERSATION_FILE, conversation.model_dump())

        # 更新meta的updated_at
        self.update_meta(task_id, {"updated_at": datetime.now()})

        logger.info(
            "message_added",
            task_id=task_id,
            message_id=message_id,
            role=role,
            content_length=len(content),
        )

        return message_id

    def get_decisions(self, task_id: str) -> List[Decision]:
        """获取决策记录"""
        task_dir = self._get_task_dir(task_id)
        data = self._read_json(task_dir / self.DECISIONS_FILE)
        if not data:
            return []

        decisions_log = DecisionLog(**data)
        return decisions_log.decisions

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
        """添加决策记录"""
        task_dir = self._get_task_dir(task_id)

        # 读取现有决策
        data = self._read_json(task_dir / self.DECISIONS_FILE)
        if data:
            decisions_log = DecisionLog(**data)
        else:
            decisions_log = DecisionLog(decisions=[])

        # 创建新决策
        decision_id = f"dec_{len(decisions_log.decisions) + 1:03d}"
        decision = Decision(
            id=decision_id,
            decision_type=DecisionType(decision_type),
            context=context,
            options=options,
            selected=selected,
            reason=reason,
            timestamp=datetime.now(),
            user_confirmed=user_confirmed,
            source=source,
        )

        decisions_log.decisions.append(decision)

        # 保存
        self._write_json(task_dir / self.DECISIONS_FILE, decisions_log.model_dump())

        logger.info(
            "decision_added",
            task_id=task_id,
            decision_id=decision_id,
            decision_type=decision_type,
            selected=selected,
        )

        return decision_id

    def get_context(self, task_id: str) -> str:
        """构建并获取任务的完整上下文"""
        parts = []

        # 1. 任务元信息
        meta = self.get_meta(task_id)
        if not meta:
            return f"# 任务不存在\n任务ID: {task_id}"

        parts.append(f"# 任务信息")
        parts.append(f"- 任务ID: {meta.task_id}")
        parts.append(f"- 任务名称: {meta.task_name}")
        parts.append(f"- 任务类型: {meta.task_type}")
        parts.append(f"- 状态: {meta.status.value}")
        parts.append(f"- 创建时间: {meta.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        parts.append(f"- 关联文档: {', '.join(meta.source_documents) or '无'}")

        # 2. 当前状态
        state = self.get_state(task_id)
        if state:
            parts.append(f"\n# 当前状态")
            parts.append(f"- 状态: {state.current_state.value}")
            if state.pending_action:
                parts.append(f"- 待执行: {state.pending_action}")

        # 3. 对话历史（最近10轮）
        messages = self.get_messages(task_id, limit=20)
        if messages:
            parts.append(f"\n# 对话历史")
            for msg in messages:
                role_name = "用户" if msg.role == MessageRole.USER else "助手"
                parts.append(f"**{role_name}**: {msg.content}")

        # 4. 关键决策
        decisions = self.get_decisions(task_id)
        if decisions:
            parts.append(f"\n# 已做决策")
            for dec in decisions:
                parts.append(f"- [{dec.decision_type.value}] {dec.selected}")
                if dec.reason:
                    parts.append(f"  原因: {dec.reason}")

        return "\n".join(parts)

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TaskMeta]:
        """列出任务"""
        tasks = []

        for task_dir in self.base_dir.iterdir():
            if not task_dir.is_dir():
                continue

            meta_file = task_dir / self.META_FILE
            if not meta_file.exists():
                continue

            data = self._read_json(meta_file)
            if data:
                meta = TaskMeta(**data)
                # 按状态过滤
                if status and meta.status != status:
                    continue
                tasks.append(meta)

        # 按创建时间倒序排列
        tasks.sort(key=lambda x: x.created_at, reverse=True)

        # 应用offset和limit
        return tasks[offset:offset + limit]

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        import shutil

        task_dir = self._get_task_dir(task_id)
        if not task_dir.exists():
            logger.warning("task_not_found_for_delete", task_id=task_id)
            return False

        try:
            shutil.rmtree(task_dir)
            logger.info("task_deleted", task_id=task_id)
            return True
        except Exception as e:
            logger.error("task_delete_failed", task_id=task_id, error=str(e))
            return False

    def task_exists(self, task_id: str) -> bool:
        """检查任务是否存在"""
        task_dir = self._get_task_dir(task_id)
        return task_dir.exists() and (task_dir / self.META_FILE).exists()

    def get_artifacts_dir(self, task_id: str) -> Optional[str]:
        """获取任务的artifacts目录路径"""
        if not self.task_exists(task_id):
            return None

        task_dir = self._get_task_dir(task_id)
        artifacts_dir = task_dir / self.ARTIFACTS_DIR
        artifacts_dir.mkdir(exist_ok=True)

        return str(artifacts_dir)
