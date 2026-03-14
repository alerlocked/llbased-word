"""
工艺文件辅助编辑系统 - Agent模块

三层架构：
- Orchestrator层: 主控Agent，负责意图识别、任务分解、协调Agent
- Functional Agent层: 撰写/校对/审查Agent，负责具体业务逻辑
- Tool层: 底层工具，单一职责，可插拔

使用方式：
```python
from app.agents.core import AgentRegistry, ToolRegistry
from app.agents.functional import discover_agents

# 自动发现并注册所有Agent
discover_agents()

# 创建Agent实例
writing_agent = AgentRegistry.create("writing")
proofread_agent = AgentRegistry.create("proofread")
review_agent = AgentRegistry.create("review")
```
"""
from app.shared.logging import get_logger

logger = get_logger(__name__)
logger.info("agents_module_initialized")

# 导出核心组件
from app.agents.core import (
    AgentRegistry,
    ToolRegistry,
    WorkflowRegistry,
    discover_tools,
    discover_agents as discover_functional_agents
)

__all__ = [
    'AgentRegistry',
    'ToolRegistry',
    'WorkflowRegistry',
    'discover_tools',
    'discover_functional_agents',
]

