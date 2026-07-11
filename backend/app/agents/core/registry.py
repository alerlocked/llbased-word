"""
Agent/Tool 注册表

提供装饰器风格的自动注册机制
"""
from typing import Dict, List, Optional, Type, Any, Callable
from app.shared.logging import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """
    Tool 注册表

    使用方式:
    ```python
    @ToolRegistry.register("my_tool")
    class MyTool:
        name = "my_tool"
        description = "我的工具"
        async def execute(self, input_data, context=None): ...
    ```

    获取Tool:
    ```python
    tool_class = ToolRegistry.get("my_tool")
    tool_instance = ToolRegistry.create("my_tool", config={...})
    ```
    """

    _tools: Dict[str, Type] = {}

    @classmethod
    def register(cls, tool_name: str) -> Callable[[Type], Type]:
        """
        装饰器：注册 Tool

        Args:
            tool_name: Tool 名称（唯一标识）

        Returns:
            装饰器函数
        """
        def decorator(tool_class: Type) -> Type:
            if tool_name in cls._tools:
                logger.warning("tool_already_registered",
                             tool_name=tool_name,
                             old_class=cls._tools[tool_name].__name__,
                             new_class=tool_class.__name__)

            cls._tools[tool_name] = tool_class
            logger.info("tool_registered", tool_name=tool_name, class_name=tool_class.__name__)
            return tool_class

        return decorator

    @classmethod
    def get(cls, tool_name: str) -> Optional[Type]:
        """
        获取 Tool 类

        Args:
            tool_name: Tool 名称

        Returns:
            Tool 类，不存在则返回 None
        """
        return cls._tools.get(tool_name)

    @classmethod
    def create(cls, tool_name: str, config: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """
        创建 Tool 实例

        Args:
            tool_name: Tool 名称
            config: 配置参数

        Returns:
            Tool 实例，不存在则返回 None
        """
        tool_class = cls.get(tool_name)
        if tool_class is None:
            logger.warning("tool_not_found", tool_name=tool_name)
            return None

        try:
            instance = tool_class(config=config)
            logger.debug("tool_created", tool_name=tool_name)
            return instance
        except Exception as e:
            logger.error("tool_creation_failed", tool_name=tool_name, error=str(e))
            return None

    @classmethod
    def list_tools(cls) -> List[str]:
        """
        列出所有已注册的 Tool 名称

        Returns:
            Tool 名称列表
        """
        return list(cls._tools.keys())

    @classmethod
    def get_info(cls, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        获取 Tool 信息

        Args:
            tool_name: Tool 名称

        Returns:
            Tool 信息字典
        """
        tool_class = cls.get(tool_name)
        if tool_class is None:
            return None

        return {
            "name": getattr(tool_class, "name", tool_name),
            "description": getattr(tool_class, "description", ""),
            "class": tool_class.__name__,
            "module": tool_class.__module__,
        }

    @classmethod
    def clear(cls):
        """清空注册表（主要用于测试）"""
        cls._tools.clear()
        logger.debug("tool_registry_cleared")


class AgentRegistry:
    """
    Agent 注册表

    使用方式:
    ```python
    @AgentRegistry.register("writing")
    class WritingAgent(BaseAgent):
        name = "writing"
        description = "撰写Agent"
        tools = []
        async def process(self, task, context=None): ...
    ```

    获取Agent:
    ```python
    agent_class = AgentRegistry.get("writing")
    agent_instance = AgentRegistry.create("writing", config={...})
    ```
    """

    _agents: Dict[str, Type] = {}

    @classmethod
    def register(cls, agent_name: str) -> Callable[[Type], Type]:
        """
        装饰器：注册 Agent

        Args:
            agent_name: Agent 名称（唯一标识）

        Returns:
            装饰器函数
        """
        def decorator(agent_class: Type) -> Type:
            if agent_name in cls._agents:
                logger.warning("agent_already_registered",
                             agent_name=agent_name,
                             old_class=cls._agents[agent_name].__name__,
                             new_class=agent_class.__name__)

            cls._agents[agent_name] = agent_class
            logger.info("agent_registered", agent_name=agent_name, class_name=agent_class.__name__)
            return agent_class

        return decorator

    @classmethod
    def get(cls, agent_name: str) -> Optional[Type]:
        """
        获取 Agent 类

        Args:
            agent_name: Agent 名称

        Returns:
            Agent 类，不存在则返回 None
        """
        return cls._agents.get(agent_name)

    @classmethod
    def create(cls, agent_name: str, config: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """
        创建 Agent 实例

        Args:
            agent_name: Agent 名称
            config: 配置参数

        Returns:
            Agent 实例，不存在则返回 None
        """
        agent_class = cls.get(agent_name)
        if agent_class is None:
            logger.warning("agent_not_found", agent_name=agent_name)
            return None

        try:
            instance = agent_class(config=config)
            logger.debug("agent_created", agent_name=agent_name)
            return instance
        except Exception as e:
            logger.error("agent_creation_failed", agent_name=agent_name, error=str(e))
            return None

    @classmethod
    def list_agents(cls) -> List[str]:
        """
        列出所有已注册的 Agent 名称

        Returns:
            Agent 名称列表
        """
        return list(cls._agents.keys())

    @classmethod
    def get_info(cls, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        获取 Agent 信息

        Args:
            agent_name: Agent 名称

        Returns:
            Agent 信息字典
        """
        agent_class = cls.get(agent_name)
        if agent_class is None:
            return None

        return {
            "name": getattr(agent_class, "name", agent_name),
            "description": getattr(agent_class, "description", ""),
            "tools": getattr(agent_class, "tools", []),
            "class": agent_class.__name__,
            "module": agent_class.__module__,
        }

    @classmethod
    def clear(cls):
        """清空注册表（主要用于测试）"""
        cls._agents.clear()
        logger.debug("agent_registry_cleared")


class WorkflowRegistry:
    """
    工作流注册表

    管理预定义的工作流配置
    """

    _workflows: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register(cls, workflow_name: str, agents: List[str], description: str = "") -> None:
        """
        注册工作流

        Args:
            workflow_name: 工作流名称
            agents: Agent 执行序列
            description: 工作流描述
        """
        cls._workflows[workflow_name] = {
            "name": workflow_name,
            "agents": agents,
            "description": description,
        }
        logger.info("workflow_registered", workflow_name=workflow_name, agents=agents)

    @classmethod
    def get(cls, workflow_name: str) -> Optional[Dict[str, Any]]:
        """获取工作流配置"""
        return cls._workflows.get(workflow_name)

    @classmethod
    def list_workflows(cls) -> List[str]:
        """列出所有工作流名称"""
        return list(cls._workflows.keys())

    @classmethod
    def clear(cls):
        """清空注册表"""
        cls._workflows.clear()


# 注册默认工作流
WorkflowRegistry.register(
    "full_edit",
    ["writing", "proofread", "review"],
    "完整编辑流程：撰写 - 校对 - 审查"
)

WorkflowRegistry.register(
    "quick_edit",
    ["writing", "proofread"],
    "快速编辑流程：撰写 - 校对"
)

WorkflowRegistry.register(
    "review_only",
    ["review"],
    "仅审查流程"
)

WorkflowRegistry.register(
    "proofread_only",
    ["proofread"],
    "仅校对流程"
)
