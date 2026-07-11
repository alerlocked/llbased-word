"""
Agent/Tool 核心协议定义

使用 Protocol 定义标准接口，支持鸭子类型和运行时检查
"""
from typing import Protocol, Any, Dict, List, Optional, runtime_checkable


@runtime_checkable
class ToolProtocol(Protocol):
    """
    Tool 标准接口协议

    所有 Tool 必须实现：
    - name: 工具名称（唯一标识）
    - description: 工具描述（用于LLM理解）
    - execute(): 执行方法

    示例:
    ```python
    @ToolRegistry.register("rag_retriever")
    class RAGRetriever:
        name = "rag_retriever"
        description = "从工艺知识库检索相关信息"

        async def execute(self, query: str, context: Optional[Dict] = None) -> Dict:
            # 检索逻辑
            return {"success": True, "results": [...]}
    ```
    """

    name: str
    description: str

    async def execute(
        self,
        input_data: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行工具

        Args:
            input_data: 输入数据（类型由具体Tool定义）
            context: 执行上下文（可选）

        Returns:
            标准格式结果:
            {
                "success": bool,
                "data": Any,           # 成功时的返回数据
                "error": str,          # 失败时的错误信息
                "error_code": str,     # 错误代码
                "metadata": Dict       # 元数据（可选）
            }
        """
        ...


@runtime_checkable
class AgentProtocol(Protocol):
    """
    Agent 标准接口协议

    所有 Agent 必须实现：
    - name: Agent名称（唯一标识）
    - description: Agent描述
    - tools: 依赖的Tool名称列表
    - process(): 处理任务方法

    示例:
    ```python
    @AgentRegistry.register("writing")
    class WritingAgent(BaseAgent):
        name = "writing"
        description = "负责工艺内容的编辑、表格填充、格式调整"
        tools = []

        async def process(self, task: Dict, context: Optional[Dict] = None) -> Dict:
            # 处理逻辑
            return {"success": True, "result": ...}
    ```
    """

    name: str
    description: str
    tools: List[str]

    async def process(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理任务

        Args:
            task: 任务描述
            {
                "action": str,         # 动作类型
                "target": str,         # 目标对象
                "content": Any,        # 内容
                "requirements": str,   # 要求
            }
            context: 执行上下文（可选）

        Returns:
            标准格式结果:
            {
                "success": bool,
                "result": Any,         # 处理结果
                "suggestions": List,   # 建议（可选）
                "warnings": List,      # 警告（可选）
                "metadata": Dict       # 元数据（可选）
            }
        """
        ...


@runtime_checkable
class WorkflowProtocol(Protocol):
    """
    工作流协议

    定义 Agent 执行序列和条件
    """

    name: str
    agents: List[str]
    description: str

    def should_continue(
        self,
        current_agent: str,
        result: Dict[str, Any]
    ) -> bool:
        """
        判断是否继续执行下一个 Agent

        Args:
            current_agent: 当前 Agent 名称
            result: 当前 Agent 的执行结果

        Returns:
            True: 继续执行
            False: 停止工作流
        """
        ...

    def get_next_agent(
        self,
        current_agent: str,
        result: Dict[str, Any]
    ) -> Optional[str]:
        """
        获取下一个要执行的 Agent

        Args:
            current_agent: 当前 Agent 名称
            result: 当前 Agent 的执行结果

        Returns:
            下一个 Agent 名称，或 None 表示工作流结束
        """
        ...
