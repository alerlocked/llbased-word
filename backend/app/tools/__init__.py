"""
工艺文件辅助编辑系统 - 工具模块

包含PDF解析、术语映射、合规检查、文档生成等工具函数

支持自动发现和注册到 ToolRegistry
"""
from typing import List

__all__ = []

# Import existing tools conditionally
try:
    from .pdf_parser import PDFParser
    __all__.append("PDFParser")
except ImportError:
    pass

try:
    from .parser_selector import ParserSelector
    __all__.append("ParserSelector")
except ImportError:
    pass

try:
    from .table_merger import TableMerger
    __all__.append("TableMerger")
except ImportError:
    pass

try:
    from .table_validator import TableValidator
    __all__.append("TableValidator")
except ImportError:
    pass

try:
    from .terminology_mapper import TerminologyMapper
    __all__.append("TerminologyMapper")
except ImportError:
    pass

try:
    from .compliance_checker import ComplianceChecker
    __all__.append("ComplianceChecker")
except ImportError:
    pass


def discover_tools() -> List[str]:
    """
    自动发现并注册所有 Tool

    扫描 tools 目录下所有 *_tool.py 文件，
    导入它们以触发 @ToolRegistry.register 装饰器

    Returns:
        已注册的 Tool 名称列表
    """
    import importlib
    import pkgutil
    from app.config import settings

    tools_dir = settings.TOOLS_DIR
    registered_tools = []

    # 新的标准 Tool 文件（使用 @ToolRegistry.register 装饰器）
    tool_modules = [
        "terminology_tool",
        "compliance_tool",
    ]

    for module_name in tool_modules:
        try:
            full_module_name = f"app.tools.{module_name}"
            importlib.import_module(full_module_name)
            registered_tools.append(module_name)
        except Exception as e:
            # 静默失败，某些 tool 可能依赖未安装的库
            pass

    # 扫描其他 *_tool.py 文件
    for _, name, _ in pkgutil.iter_modules([str(tools_dir)]):
        if name.endswith("_tool") and name not in tool_modules:
            try:
                importlib.import_module(f"app.tools.{name}")
                registered_tools.append(name)
            except Exception:
                pass

    return registered_tools


def get_tool_registry():
    """
    获取 ToolRegistry 并确保所有 Tool 已注册

    Returns:
        ToolRegistry 类
    """
    from app.agents.core import ToolRegistry

    # 触发自动发现
    discover_tools()

    return ToolRegistry


# 便捷函数
def create_tool(name: str, config: dict = None):
    """
    创建 Tool 实例

    Args:
        name: Tool 名称
        config: 配置参数

    Returns:
        Tool 实例或 None
    """
    registry = get_tool_registry()
    return registry.create(name, config)


def list_available_tools() -> List[str]:
    """
    列出所有可用的 Tool

    Returns:
        Tool 名称列表
    """
    registry = get_tool_registry()
    return registry.list_tools()


# Auto-register all tools on `import app.tools`. Without this, discover_tools was
# only called inside get_tool_registry() (which nothing invoked), so ToolRegistry
# stayed empty and every agent tool raised tool_not_found at init.
discover_tools()
