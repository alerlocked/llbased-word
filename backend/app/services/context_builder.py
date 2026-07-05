"""
上下文构建器
组装完整任务上下文（任务信息+对话历史+源文档）
"""
from typing import Optional, List, Dict, Any
from pathlib import Path

from app.shared.logging import get_logger
from app.repositories.protocols import TaskMemoryRepository
from app.services.context_manager import ContextManager
from app.models.task_memory import (
    TaskMeta,
    TaskState,
    Message,
    MessageRole,
    Decision,
    ProcessState,
)

logger = get_logger(__name__)


class ContextBuilder:
    """
    上下文构建器

    将任务记忆和源文档内容组合成LLM可理解的上下文。
    支持上下文长度限制和截断策略。
    """

    def __init__(
        self,
        repository: TaskMemoryRepository,
        context_manager: Optional[ContextManager] = None,
        max_context_length: int = 32000,
    ):
        """
        初始化ContextBuilder

        Args:
            repository: 任务记忆Repository
            context_manager: 文档上下文管理器
            max_context_length: 最大上下文长度（字符数）
        """
        self.repository = repository
        self.context_manager = context_manager or ContextManager()
        self.max_context_length = max_context_length

        logger.info(
            "context_builder_initialized",
            max_context_length=max_context_length,
        )

    def build_context(
        self,
        task_id: str,
        include_documents: bool = True,
        include_history: bool = True,
        include_decisions: bool = True,
        max_history_turns: int = 10,
    ) -> str:
        """
        构建完整任务上下文

        Args:
            task_id: 任务ID
            include_documents: 是否包含源文档
            include_history: 是否包含对话历史
            include_decisions: 是否包含决策记录
            max_history_turns: 最大历史轮次

        Returns:
            格式化的上下文字符串
        """
        parts = []

        # 1. 任务基本信息
        meta = self.repository.get_meta(task_id)
        if not meta:
            return f"# 任务不存在\n任务ID: {task_id}"

        parts.append(self._format_meta(meta))

        # 2. 当前状态
        state = self.repository.get_state(task_id)
        if state:
            parts.append(self._format_state(state))

        # 3. 对话历史
        if include_history:
            messages = self.repository.get_messages(task_id, limit=max_history_turns * 2)
            if messages:
                parts.append(self._format_messages(messages))

        # 4. 决策记录
        if include_decisions:
            decisions = self.repository.get_decisions(task_id)
            if decisions:
                parts.append(self._format_decisions(decisions))

        # 5. 源文档内容
        if include_documents and meta.source_documents:
            doc_context = self._build_document_context(meta.source_documents)
            if doc_context:
                parts.append(doc_context)

        # 组合并检查长度
        context = "\n\n---\n\n".join(parts)

        # 截断处理
        if len(context) > self.max_context_length:
            context = self._truncate_context(context, self.max_context_length)

        logger.info(
            "context_built",
            task_id=task_id,
            context_length=len(context),
            included_docs=len(meta.source_documents) if meta.source_documents else 0,
        )

        return context

    def build_minimal_context(self, task_id: str) -> str:
        """
        构建最小上下文（仅任务信息和当前状态）

        用于简单查询场景
        """
        return self.build_context(
            task_id,
            include_documents=False,
            include_history=False,
            include_decisions=False,
        )

    def build_full_context(self, task_id: str) -> str:
        """
        构建完整上下文（包含所有信息）

        用于复杂推理场景
        """
        return self.build_context(
            task_id,
            include_documents=True,
            include_history=True,
            include_decisions=True,
            max_history_turns=20,
        )

    def get_document_summary(self, doc_name: str) -> str:
        """
        获取单个文档的摘要

        Args:
            doc_name: 文档名称

        Returns:
            文档摘要
        """
        return self.context_manager.get_document_markdown(doc_name)

    def _format_meta(self, meta: TaskMeta) -> str:
        """格式化任务元信息"""
        lines = [
            "# 任务信息",
            f"- **任务ID**: {meta.task_id}",
            f"- **任务名称**: {meta.task_name}",
            f"- **任务类型**: {meta.task_type}",
            f"- **状态**: {meta.status.value}",
            f"- **创建时间**: {meta.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        if meta.source_documents:
            lines.append(f"- **关联文档**: {', '.join(meta.source_documents)}")

        if meta.tags:
            lines.append(f"- **标签**: {', '.join(meta.tags)}")

        return "\n".join(lines)

    def _format_state(self, state: TaskState) -> str:
        """格式化状态信息"""
        current = state.current_state
        state_value = current.value if isinstance(current, ProcessState) else str(current)

        lines = [
            "# 当前状态",
            f"- **状态**: {state_value}",
        ]

        if state.pending_action:
            action_desc = state.pending_action.get("description", "")
            if action_desc:
                lines.append(f"- **待执行**: {action_desc}")

        # 最近的状态转换
        if state.state_history:
            recent = state.state_history[-3:]  # 最近3次
            lines.append("\n**最近状态转换**:")
            for trans in recent:
                from_val = trans.from_state.value if hasattr(trans.from_state, "value") else trans.from_state
                to_val = trans.to_state.value if hasattr(trans.to_state, "value") else trans.to_state
                lines.append(f"  - {from_val} → {to_val}")

        return "\n".join(lines)

    def _format_messages(self, messages: List[Message]) -> str:
        """格式化对话历史"""
        lines = ["# 对话历史"]

        for msg in messages:
            role = msg.role
            role_name = "用户" if role == MessageRole.USER or role == "user" else "助手"
            content = msg.content
            # 截断过长内容
            if len(content) > 500:
                content = content[:500] + "..."

            lines.append(f"\n**{role_name}**: {content}")

            # 如果有元数据，添加引用信息
            if msg.metadata:
                refs = msg.metadata.get("tables_referenced", [])
                if refs:
                    lines.append(f"  [引用表格: {', '.join(refs)}]")

        return "\n".join(lines)

    def _format_decisions(self, decisions: List[Decision]) -> str:
        """格式化决策记录"""
        lines = ["# 已做决策"]

        for dec in decisions:
            dec_type = dec.decision_type
            type_value = dec_type.value if hasattr(dec_type, "value") else str(dec_type)
            lines.append(f"\n## {type_value}")
            lines.append(f"- **上下文**: {dec.context}")
            lines.append(f"- **选择**: {dec.selected}")
            if dec.reason:
                lines.append(f"- **原因**: {dec.reason}")
            if dec.user_confirmed:
                lines.append(f"- **用户已确认**: 是")

        return "\n".join(lines)

    def _build_document_context(self, doc_names: List[str]) -> str:
        """构建文档上下文"""
        return self.context_manager.build_document_context(
            doc_names,
            include_html=False,
            max_tables=30,
        )

    def _truncate_context(self, context: str, max_length: int) -> str:
        """
        截断上下文

        优先保留：任务信息 > 当前状态 > 决策记录 > 对话历史（最近） > 文档
        """
        if len(context) <= max_length:
            return context

        # 简单截断：保留前80%
        truncated = context[:int(max_length * 0.8)]
        truncated += "\n\n... [上下文已截断，保留关键信息]"

        logger.warning(
            "context_truncated",
            original_length=len(context),
            truncated_length=len(truncated),
        )

        return truncated

    def estimate_tokens(self, context: str) -> int:
        """
        估算上下文的Token数量

        粗略估计：中文约1.5字符/token，英文约4字符/token
        """
        # 简单估计
        chinese_chars = sum(1 for c in context if '\u4e00' <= c <= '\u9fff')
        other_chars = len(context) - chinese_chars

        estimated_tokens = int(chinese_chars / 1.5 + other_chars / 4)

        return estimated_tokens
