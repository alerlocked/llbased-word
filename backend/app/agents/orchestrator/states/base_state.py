"""
工艺文件辅助编辑系统 - 状态基类
定义所有状态的公共接口和行为
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum

from app.shared.logging import get_logger

logger = get_logger(__name__)


class StateType(Enum):
    """状态类型枚举"""
    EDITING = "editing"  # 编辑状态
    REVIEW = "review"    # 审核状态
    GENERATION = "generation"  # 生成状态


class BaseState(ABC):
    """
    状态基类

    所有具体状态都应该继承这个基类，
    实现状态特定的行为和转换逻辑
    """

    def __init__(self, state_type: StateType, context: Optional[Dict[str, Any]] = None):
        """
        初始化状态

        Args:
            state_type: 状态类型
            context: 状态上下文
        """
        self.state_type = state_type
        self.context = context or {}
        self.entered_at: Optional[str] = None
        self.exited_at: Optional[str] = None

        logger.debug(f"state_initialized", state_type=state_type.value)

    @abstractmethod
    async def on_enter(self, previous_state: Optional['BaseState'] = None):
        """
        进入状态时的处理

        Args:
            previous_state: 前一个状态
        """
        pass

    @abstractmethod
    async def on_exit(self, next_state: Optional['BaseState'] = None):
        """
        退出状态时的处理

        Args:
            next_state: 下一个状态
        """
        pass

    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理状态相关的输入

        Args:
            input_data: 输入数据

        Returns:
            处理结果
        """
        pass

    @abstractmethod
    def can_transition_to(self, target_state_type: StateType) -> bool:
        """
        检查是否可以转换到目标状态

        Args:
            target_state_type: 目标状态类型

        Returns:
            是否可以转换
        """
        pass

    def update_context(self, updates: Dict[str, Any]):
        """
        更新状态上下文

        Args:
            updates: 要更新的内容
        """
        self.context.update(updates)
        logger.debug(f"state_context_updated", state_type=self.state_type.value, update_keys=list(updates.keys()))

    def get_context(self) -> Dict[str, Any]:
        """
        获取状态上下文

        Returns:
            上下文副本
        """
        return self.context.copy()

    def get_state_info(self) -> Dict[str, Any]:
        """
        获取状态信息

        Returns:
            状态信息字典
        """
        return {
            "type": self.state_type.value,
            "entered_at": self.entered_at,
            "exited_at": self.exited_at,
            "context_keys": list(self.context.keys()),
            "duration": self._calculate_duration()
        }

    def _calculate_duration(self) -> Optional[float]:
        """
        计算状态持续时间（秒）

        Returns:
            持续时间（秒），如果状态未进入或未退出则返回None
        """
        if not self.entered_at:
            return None

        from datetime import datetime
        entered_time = datetime.fromisoformat(self.entered_at)
        exit_time = datetime.fromisoformat(self.exited_at) if self.exited_at else datetime.now()

        duration = (exit_time - entered_time).total_seconds()
        return duration

    def _log_state_transition(self, action: str, target_state: Optional['BaseState'] = None):
        """
        记录状态转换日志

        Args:
            action: 动作描述
            target_state: 目标状态
        """
        target_type = target_state.state_type.value if target_state else "none"
        logger.info(
            f"state_transition_{action}",
            from_state=self.state_type.value,
            to_state=target_type,
            duration=self._calculate_duration()
        )