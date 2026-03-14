"""
功能 Agent 模块

包含三个核心功能 Agent:
- WritingAgent: 撰写（工艺内容编辑）
- ProofreadAgent: 校对（术语标准化、数据纠正）
- ReviewAgent: 审查（合规性检查、风险评估）
"""
from typing import List

__all__ = []


def discover_agents() -> List[str]:
    """
    自动发现并注册所有功能 Agent

    导入所有 *_agent.py 文件以触发 @AgentRegistry.register 装饰器

    Returns:
        已注册的 Agent 名称列表
    """
    import importlib

    agent_modules = [
        "writing_agent",
        "proofread_agent",
        "review_agent"
    ]

    registered = []

    for module_name in agent_modules:
        try:
            full_module_name = f"app.agents.functional.{module_name}"
            importlib.import_module(full_module_name)
            registered.append(module_name.replace("_agent", ""))
        except Exception as e:
            # 静默失败
            pass

    return registered


def get_agent_registry():
    """
    获取 AgentRegistry 并确保所有 Agent 已注册

    Returns:
        AgentRegistry 类
    """
    from app.agents.core import AgentRegistry

    # 触发自动发现
    discover_agents()

    return AgentRegistry


def create_agent(name: str, config: dict = None):
    """
    创建 Agent 实例

    Args:
        name: Agent 名称
        config: 配置参数

    Returns:
        Agent 实例或 None
    """
    registry = get_agent_registry()
    return registry.create(name, config)


def list_available_agents() -> List[str]:
    """
    列出所有可用的 Agent

    Returns:
        Agent 名称列表
    """
    registry = get_agent_registry()
    return registry.list_agents()


# 延迟导入
def get_writing_agent(config: dict = None):
    """获取 WritingAgent 实例"""
    from .writing_agent import WritingAgent
    return WritingAgent(config)


def get_proofread_agent(config: dict = None):
    """获取 ProofreadAgent 实例"""
    from .proofread_agent import ProofreadAgent
    return ProofreadAgent(config)


def get_review_agent(config: dict = None):
    """获取 ReviewAgent 实例"""
    from .review_agent import ReviewAgent
    return ReviewAgent(config)
