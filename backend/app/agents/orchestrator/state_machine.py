"""
工艺文件辅助编辑系统 - 状态机管理
管理工艺文件编辑流程的不同状态

支持两种模式：
1. 内存模式：纯内存操作，不持久化
2. Repository模式：底层使用Repository持久化
"""
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from app.shared.logging import get_logger

logger = get_logger(__name__)


class ProcessState(Enum):
    """工艺文件编辑流程状态"""
    IDLE = "idle"  # 空闲状态
    INTENT_RECOGNITION = "intent_recognition"  # 意图识别
    INFO_ASSESSMENT = "info_assessment"  # 信息完整性评估
    INFO_COLLECTION = "info_collection"  # 信息收集（等待用户输入）
    PREVIEW_GENERATION = "preview_generation"  # 预览生成
    USER_CONFIRMATION = "user_confirmation"  # 用户确认
    TASK_DECOMPOSITION = "task_decomposition"  # 任务分解
    TASK_EXECUTION = "task_execution"  # 任务执行
    RESULT_AGGREGATION = "result_aggregation"  # 结果聚合
    USER_REVIEW = "user_review"  # 用户审核
    COMPLETION = "completion"  # 完成
    ERROR = "error"  # 错误
    PAUSED = "paused"  # 暂停（等待外部输入）


@dataclass
class StateTransition:
    """状态转换规则"""
    from_state: ProcessState
    to_state: ProcessState
    condition: Optional[str] = None  # 转换条件


class ProcessStateMachine:
    """
    工艺文件编辑状态机

    管理工艺文件编辑流程的状态转换，确保流程的完整性。

    使用方式：
    ```python
    # 内存模式（向后兼容）
    sm = ProcessStateMachine()

    # Repository模式（推荐）
    from app.repositories import get_repository
    repo = get_repository()
    sm = ProcessStateMachine(repository=repo, task_id="电缆装配_20260224")
    ```
    """

    # 允许的状态转换（包含新的交互流程）
    VALID_TRANSITIONS = [
        # 基础流程
        StateTransition(ProcessState.IDLE, ProcessState.INTENT_RECOGNITION),

        # 新的交互流程
        StateTransition(ProcessState.INTENT_RECOGNITION, ProcessState.INFO_ASSESSMENT),  # 意图识别后评估信息
        StateTransition(ProcessState.INFO_ASSESSMENT, ProcessState.INFO_COLLECTION),  # 需要收集信息
        StateTransition(ProcessState.INFO_ASSESSMENT, ProcessState.PREVIEW_GENERATION),  # 信息完整，生成预览
        StateTransition(ProcessState.INFO_COLLECTION, ProcessState.PAUSED),  # 等待用户输入
        StateTransition(ProcessState.PAUSED, ProcessState.INFO_COLLECTION),  # 用户补充后继续收集
        StateTransition(ProcessState.INFO_COLLECTION, ProcessState.PREVIEW_GENERATION),  # 收集完成，生成预览
        StateTransition(ProcessState.PREVIEW_GENERATION, ProcessState.USER_CONFIRMATION),  # 预览完成，等待确认
        StateTransition(ProcessState.USER_CONFIRMATION, ProcessState.PAUSED),  # 等待用户确认
        StateTransition(ProcessState.PAUSED, ProcessState.USER_CONFIRMATION),  # 继续确认
        StateTransition(ProcessState.USER_CONFIRMATION, ProcessState.TASK_DECOMPOSITION),  # 确认后开始任务分解
        StateTransition(ProcessState.USER_CONFIRMATION, ProcessState.INFO_COLLECTION),  # 用户要求修改

        # 兼容旧流程（信息完整时可直接跳过交互环节）
        StateTransition(ProcessState.INTENT_RECOGNITION, ProcessState.TASK_DECOMPOSITION),
        StateTransition(ProcessState.INFO_ASSESSMENT, ProcessState.TASK_DECOMPOSITION),

        # 任务执行流程
        StateTransition(ProcessState.TASK_DECOMPOSITION, ProcessState.TASK_EXECUTION),
        StateTransition(ProcessState.TASK_EXECUTION, ProcessState.RESULT_AGGREGATION),
        StateTransition(ProcessState.RESULT_AGGREGATION, ProcessState.USER_REVIEW),
        StateTransition(ProcessState.USER_REVIEW, ProcessState.COMPLETION),

        # 错误状态可以从任何状态转换
        StateTransition(ProcessState.IDLE, ProcessState.ERROR),
        StateTransition(ProcessState.INTENT_RECOGNITION, ProcessState.ERROR),
        StateTransition(ProcessState.INFO_ASSESSMENT, ProcessState.ERROR),
        StateTransition(ProcessState.INFO_COLLECTION, ProcessState.ERROR),
        StateTransition(ProcessState.PREVIEW_GENERATION, ProcessState.ERROR),
        StateTransition(ProcessState.USER_CONFIRMATION, ProcessState.ERROR),
        StateTransition(ProcessState.TASK_DECOMPOSITION, ProcessState.ERROR),
        StateTransition(ProcessState.TASK_EXECUTION, ProcessState.ERROR),
        StateTransition(ProcessState.RESULT_AGGREGATION, ProcessState.ERROR),
        StateTransition(ProcessState.USER_REVIEW, ProcessState.ERROR),
        StateTransition(ProcessState.PAUSED, ProcessState.ERROR),

        # 从错误状态可以回到空闲状态
        StateTransition(ProcessState.ERROR, ProcessState.IDLE),

        # 用户审核后可能需要重新执行某些步骤
        StateTransition(ProcessState.USER_REVIEW, ProcessState.TASK_EXECUTION),
        StateTransition(ProcessState.USER_REVIEW, ProcessState.TASK_DECOMPOSITION),

        # 从暂停状态可以取消
        StateTransition(ProcessState.PAUSED, ProcessState.IDLE),
    ]

    def __init__(
        self,
        repository=None,
        task_id: Optional[str] = None,
    ):
        """
        初始化状态机

        Args:
            repository: TaskMemoryRepository实例（可选）
            task_id: 关联的任务ID（使用Repository时需要）
        """
        self.repository = repository
        self.task_id = task_id

        # 内存状态
        self.current_state = ProcessState.IDLE
        self.state_history: List[Dict[str, Any]] = [{
            "state": self.current_state.value,
            "timestamp": datetime.now().isoformat(),
            "trigger": "init"
        }]
        self.context: Dict[str, Any] = {}

        # 如果有Repository且task_id，尝试从Repository恢复状态
        if self.repository and self.task_id:
            self._load_from_repository()

        logger.info(
            "state_machine_initialized",
            initial_state=self.current_state.value,
            has_repository=repository is not None,
            task_id=task_id,
        )

    def _load_from_repository(self):
        """从Repository加载状态"""
        try:
            state_data = self.repository.get_state(self.task_id)
            if state_data:
                # 恢复当前状态
                if hasattr(state_data, 'current_state'):
                    state_val = state_data.current_state
                    if isinstance(state_val, str):
                        self.current_state = ProcessState(state_val)
                    else:
                        self.current_state = state_val

                # 恢复状态历史
                if hasattr(state_data, 'state_history') and state_data.state_history:
                    self.state_history = []
                    for trans in state_data.state_history:
                        self.state_history.append({
                            "from_state": trans.from_state if isinstance(trans.from_state, str) else trans.from_state.value,
                            "to_state": trans.to_state if isinstance(trans.to_state, str) else trans.to_state.value,
                            "timestamp": trans.timestamp.isoformat() if hasattr(trans.timestamp, 'isoformat') else str(trans.timestamp),
                            "trigger": trans.trigger,
                        })

                # 恢复上下文
                if hasattr(state_data, 'context'):
                    self.context = state_data.context or {}

                logger.info(
                    "state_loaded_from_repository",
                    current_state=self.current_state.value,
                    history_count=len(self.state_history),
                )
        except Exception as e:
            logger.warning("state_load_from_repository_failed", error=str(e))

    def _save_to_repository(self, trigger: Optional[str] = None):
        """保存状态到Repository"""
        if not self.repository or not self.task_id:
            return

        try:
            self.repository.update_state(
                task_id=self.task_id,
                new_state=self.current_state,
                context_update=self.context if self.context else None,
            )
            logger.debug("state_saved_to_repository", state=self.current_state.value)
        except Exception as e:
            logger.error("state_save_to_repository_failed", error=str(e))

    async def transition_to(
        self,
        new_state: ProcessState,
        context_update: Optional[Dict[str, Any]] = None,
        trigger: Optional[str] = None,
    ) -> bool:
        """
        尝试转换到新状态

        Args:
            new_state: 目标状态
            context_update: 状态上下文更新
            trigger: 触发转换的原因

        Returns:
            是否成功转换
        """
        # 检查转换是否有效
        if not self._is_valid_transition(self.current_state, new_state):
            logger.warning(
                "invalid_state_transition",
                from_state=self.current_state.value,
                to_state=new_state.value
            )
            return False

        # 更新上下文
        if context_update:
            self.context.update(context_update)

        # 执行状态转换
        old_state = self.current_state
        self.current_state = new_state

        # 记录状态转换
        transition_record = {
            "from_state": old_state.value,
            "to_state": new_state.value,
            "timestamp": datetime.now().isoformat(),
            "trigger": trigger,
        }
        self.state_history.append(transition_record)

        # 持久化到Repository
        self._save_to_repository(trigger)

        logger.info(
            "state_transition",
            from_state=old_state.value,
            to_state=new_state.value,
            trigger=trigger,
            context_keys=list(self.context.keys())
        )

        # 执行状态进入动作
        await self._on_state_enter(new_state, old_state)

        return True

    def _is_valid_transition(self, from_state: ProcessState, to_state: ProcessState) -> bool:
        """
        检查状态转换是否有效

        Args:
            from_state: 起始状态
            to_state: 目标状态

        Returns:
            转换是否有效
        """
        # 相同状态转换总是允许的
        if from_state == to_state:
            return True

        # 检查预定义的转换规则
        for transition in self.VALID_TRANSITIONS:
            if transition.from_state == from_state and transition.to_state == to_state:
                return True

        return False

    async def _on_state_enter(self, new_state: ProcessState, old_state: ProcessState):
        """
        状态进入时的处理

        Args:
            new_state: 新状态
            old_state: 旧状态
        """
        # 这里可以添加状态特定的处理逻辑
        if new_state == ProcessState.INTENT_RECOGNITION:
            logger.info("entering_intent_recognition")
            # 可以在这里初始化意图识别相关的资源

        elif new_state == ProcessState.INFO_ASSESSMENT:
            logger.info("entering_info_assessment", intent_type=self.context.get("intent", {}).get("type"))

        elif new_state == ProcessState.INFO_COLLECTION:
            logger.info("entering_info_collection",
                      missing_count=len(self.context.get("missing_info", {}).get("high_priority", [])))

        elif new_state == ProcessState.PREVIEW_GENERATION:
            logger.info("entering_preview_generation")

        elif new_state == ProcessState.USER_CONFIRMATION:
            logger.info("entering_user_confirmation", preview_generated="preview" in self.context)

        elif new_state == ProcessState.PAUSED:
            logger.info("entering_paused", reason=self.context.get("pause_reason", "waiting_for_input"))

        elif new_state == ProcessState.TASK_EXECUTION:
            logger.info("entering_task_execution", task_count=len(self.context.get("tasks", [])))

        elif new_state == ProcessState.USER_REVIEW:
            logger.info("entering_user_review")

        elif new_state == ProcessState.COMPLETION:
            logger.info("entering_completion")
            # 清理临时资源等

        elif new_state == ProcessState.ERROR:
            logger.error("entering_error_state", old_state=old_state.value)

    def get_current_state(self) -> ProcessState:
        """获取当前状态"""
        return self.current_state

    def get_state_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取状态历史

        Args:
            limit: 返回的最大记录数

        Returns:
            状态历史列表
        """
        return self.state_history[-limit:]

    def get_context(self) -> Dict[str, Any]:
        """获取状态上下文"""
        return self.context.copy()

    def update_context(self, updates: Dict[str, Any]):
        """
        更新状态上下文

        Args:
            updates: 要更新的内容
        """
        self.context.update(updates)
        logger.debug("context_updated", update_keys=list(updates.keys()))

        # 同步到Repository
        if self.repository and self.task_id:
            self._save_to_repository(trigger="context_update")

    async def reset(self):
        """重置状态机到初始状态"""
        old_state = self.current_state
        self.current_state = ProcessState.IDLE
        self.state_history = [{
            "state": self.current_state.value,
            "timestamp": datetime.now().isoformat(),
            "trigger": "reset"
        }]
        self.context.clear()

        # 同步到Repository
        if self.repository and self.task_id:
            self._save_to_repository(trigger="reset")

        logger.info("state_machine_reset", from_state=old_state.value)

    def can_transition_to(self, state: ProcessState) -> bool:
        """
        检查是否可以转换到指定状态

        Args:
            state: 目标状态

        Returns:
            是否可以转换
        """
        return self._is_valid_transition(self.current_state, state)

    def get_available_transitions(self) -> List[ProcessState]:
        """
        获取当前状态下可用的转换目标

        Returns:
            可转换到的状态列表
        """
        available = []
        for transition in self.VALID_TRANSITIONS:
            if transition.from_state == self.current_state:
                available.append(transition.to_state)
        return list(set(available))  # 去重

    def set_task(self, task_id: str):
        """
        设置关联的任务ID

        Args:
            task_id: 任务ID
        """
        self.task_id = task_id
        # 尝试从Repository加载状态
        if self.repository:
            self._load_from_repository()
        logger.info("state_machine_task_set", task_id=task_id)

    def get_current_state(self) -> ProcessState:
        """获取当前状态（兼容方法）"""
        return self.current_state

    async def transition_to(
        self,
        new_state,
        context_update: Optional[Dict[str, Any]] = None,
        trigger: Optional[str] = None,
    ) -> bool:
        """
        尝试转换到新状态（支持字符串或枚举）

        Args:
            new_state: 目标状态（字符串或ProcessState枚举）
            context_update: 状态上下文更新
            trigger: 触发转换的原因

        Returns:
            是否成功转换
        """
        # 支持字符串输入
        if isinstance(new_state, str):
            new_state = ProcessState(new_state)

        return await self._transition_to_internal(new_state, context_update, trigger)

    async def _transition_to_internal(
        self,
        new_state: ProcessState,
        context_update: Optional[Dict[str, Any]] = None,
        trigger: Optional[str] = None,
    ) -> bool:
        """内部状态转换实现"""
        # 检查转换是否有效
        if not self._is_valid_transition(self.current_state, new_state):
            logger.warning(
                "invalid_state_transition",
                from_state=self.current_state.value,
                to_state=new_state.value
            )
            return False

        # 更新上下文
        if context_update:
            self.context.update(context_update)

        # 执行状态转换
        old_state = self.current_state
        self.current_state = new_state

        # 记录状态转换
        transition_record = {
            "from_state": old_state.value,
            "to_state": new_state.value,
            "timestamp": datetime.now().isoformat(),
            "trigger": trigger,
        }
        self.state_history.append(transition_record)

        # 持久化到Repository
        self._save_to_repository(trigger)

        logger.info(
            "state_transition",
            from_state=old_state.value,
            to_state=new_state.value,
            trigger=trigger,
            context_keys=list(self.context.keys())
        )

        # 执行状态进入动作
        await self._on_state_enter(new_state, old_state)

        return True

    def get_state_summary(self) -> Dict[str, Any]:
        """
        获取状态摘要

        Returns:
            状态摘要信息
        """
        return {
            "current_state": self.current_state.value,
            "context_keys": list(self.context.keys()),
            "history_count": len(self.state_history),
            "available_transitions": [s.value for s in self.get_available_transitions()],
        }
