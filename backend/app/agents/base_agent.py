"""
Agent 基类

提供 Agent 的通用实现
"""
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

from app.agents.core import AgentRegistry, ToolRegistry, ToolProtocol
from app.shared.logging import get_logger

logger = get_logger(__name__)


class BaseAgent(ABC):
    """
    Agent 基类

    提供通用功能：
    - Tool 初始化和管理
    - 日志记录
    - 错误处理

    子类需要实现：
    - name: Agent 名称
    - description: Agent 描述
    - tools: 依赖的 Tool 列表
    - process(): 核心处理逻辑
    """

    name: str = "base_agent"
    description: str = ""
    tools: List[str] = []

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化 Agent

        Args:
            config: 配置参数
        """
        self.config = config or {}
        self._tools: Dict[str, Any] = {}
        self._init_tools()

        logger.info(
            "agent_initialized",
            agent_name=self.name,
            tools=self.tools
        )

    def _init_tools(self):
        """
        初始化依赖的 Tools

        从 ToolRegistry 获取 Tool 实例
        """
        for tool_name in self.tools:
            tool_config = self.config.get(tool_name, {})
            tool = ToolRegistry.create(tool_name, tool_config)

            if tool is not None:
                self._tools[tool_name] = tool
                logger.debug(
                    "tool_initialized",
                    agent_name=self.name,
                    tool_name=tool_name
                )
            else:
                logger.warning(
                    "tool_not_found",
                    agent_name=self.name,
                    tool_name=tool_name
                )

    def get_tool(self, tool_name: str) -> Optional[Any]:
        """
        获取 Tool 实例

        Args:
            tool_name: Tool 名称

        Returns:
            Tool 实例或 None
        """
        return self._tools.get(tool_name)

    async def use_tool(
        self,
        tool_name: str,
        input_data: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        调用 Tool

        Args:
            tool_name: Tool 名称
            input_data: 输入数据
            context: 执行上下文

        Returns:
            Tool 执行结果

        Raises:
            ValueError: Tool 不存在
        """
        tool = self.get_tool(tool_name)

        if tool is None:
            logger.error(
                "tool_not_available",
                agent_name=self.name,
                tool_name=tool_name
            )
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not available",
                "error_code": "TOOL_NOT_FOUND"
            }

        try:
            logger.debug(
                "tool_execution_started",
                agent_name=self.name,
                tool_name=tool_name
            )

            # 调用 Tool 的 execute 方法
            if hasattr(tool, 'execute'):
                result = await tool.execute(input_data, context)
            else:
                # 兼容旧版 Tool
                result = await tool(input_data, context)

            logger.debug(
                "tool_execution_completed",
                agent_name=self.name,
                tool_name=tool_name,
                success=result.get("success", False)
            )

            return result

        except Exception as e:
            logger.error(
                "tool_execution_failed",
                agent_name=self.name,
                tool_name=tool_name,
                error=str(e)
            )
            return {
                "success": False,
                "error": str(e),
                "error_code": "TOOL_EXECUTION_FAILED"
            }

    @abstractmethod
    async def process(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理任务（抽象方法，子类必须实现）

        Args:
            task: 任务描述
            context: 执行上下文

        Returns:
            处理结果
        """
        pass

    async def execute(
        self,
        input_data: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行 Agent（标准接口方法）

        Args:
            input_data: 输入数据
            context: 执行上下文

        Returns:
            执行结果
        """
        try:
            # 将 input_data 转换为 task 格式
            if isinstance(input_data, dict):
                task = input_data
            elif isinstance(input_data, str):
                task = {"content": input_data}
            else:
                task = {"data": input_data}

            # 调用 process 方法
            result = await self.process(task, context)

            # 确保返回标准格式
            if not isinstance(result, dict):
                result = {"success": True, "result": result}

            if "success" not in result:
                result["success"] = True

            return result

        except Exception as e:
            logger.error(
                "agent_execution_failed",
                agent_name=self.name,
                error=str(e)
            )
            return {
                "success": False,
                "error": str(e),
                "error_code": "AGENT_EXECUTION_FAILED"
            }

    def get_info(self) -> Dict[str, Any]:
        """
        获取 Agent 信息

        Returns:
            Agent 信息字典
        """
        return {
            "name": self.name,
            "description": self.description,
            "tools": self.tools,
            "available_tools": list(self._tools.keys())
        }
