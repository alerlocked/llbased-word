"""
Agent/Tool 核心模块

提供模块化的 Agent/Tool 架构：
- Protocol: 标准接口定义
- Registry: 注册表和装饰器
- Workflow: 工作流管理
"""

from .protocols import (
    ToolProtocol,
    AgentProtocol,
    WorkflowProtocol,
    runtime_checkable,
)

from .registry import (
    ToolRegistry,
    AgentRegistry,
    WorkflowRegistry,
)

__all__ = [
    # Protocols
    "ToolProtocol",
    "AgentProtocol",
    "WorkflowProtocol",
    "runtime_checkable",

    # Registries
    "ToolRegistry",
    "AgentRegistry",
    "WorkflowRegistry",
]


def discover_tools():
    """
    自动发现并注册所有 Tool

    扫描 app/tools/ 目录下所有 *_tool.py 文件
    """
    import importlib
    import pkgutil
    from pathlib import Path

    tools_dir = Path(__file__).parent.parent.parent / "tools"

    if not tools_dir.exists():
        return

    for _, name, _ in pkgutil.iter_modules([str(tools_dir)]):
        if name.endswith("_tool") or name in ["rag_retriever", "terminology", "compliance", "document"]:
            try:
                importlib.import_module(f"app.tools.{name}")
            except Exception as e:
                # 静默失败，某些tool可能依赖未安装的库
                pass


def discover_agents():
    """
    自动发现并注册所有 Agent

    扫描 app/agents/functional/ 目录下所有 *_agent.py 文件
    """
    import importlib
    import pkgutil
    from pathlib import Path

    agents_dir = Path(__file__).parent.parent / "functional"

    if not agents_dir.exists():
        return

    for _, name, _ in pkgutil.iter_modules([str(agents_dir)]):
        if name.endswith("_agent") or name in ["writing", "proofread", "review"]:
            try:
                importlib.import_module(f"app.agents.functional.{name}")
            except Exception as e:
                # 静默失败
                pass


def init_registry():
    """
    初始化注册表

    自动发现并注册所有 Tool 和 Agent
    """
    discover_tools()
    discover_agents()
