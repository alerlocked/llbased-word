"""
表格提取器模块

提供多种表格提取器实现，根据文档复杂度自动选择最佳解析器。

可用的提取器：
- BaseTableExtractor: 抽象基类，定义统一接口
- PDFPlumberTableExtractor: 基于pdfplumber的表格提取器
- MinerUTableExtractor: 基于MinerU TableFormer的高精度表格提取器（可选依赖）
"""
from app.tools.table_extractors.base_extractor import BaseTableExtractor
from app.tools.table_extractors.pdfplumber_extractor import PDFPlumberTableExtractor

# 尝试导入MinerU提取器（可选依赖）
# 如果MinerU未安装，将不会报错，只是该提取器不可用
_mineru_available = False
try:
    from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor
    _mineru_available = True
    __all__ = ['BaseTableExtractor', 'PDFPlumberTableExtractor', 'MinerUTableExtractor']
except ImportError:
    # MinerU未安装，仅提供基础提取器
    __all__ = ['BaseTableExtractor', 'PDFPlumberTableExtractor']


def get_available_extractors() -> dict:
    """
    获取所有可用的提取器

    Returns:
        字典，键为提取器名称，值为提取器类
    """
    extractors = {
        'pdfplumber': PDFPlumberTableExtractor,
    }

    if _mineru_available:
        extractors['mineru'] = MinerUTableExtractor

    return extractors


def get_best_extractor(config: dict = None, prefer_mineru: bool = True) -> BaseTableExtractor:
    """
    获取最佳可用的提取器

    Args:
        config: 配置字典
        prefer_mineru: 是否优先使用MinerU

    Returns:
        提取器实例
    """
    if prefer_mineru and _mineru_available:
        return MinerUTableExtractor(config)

    return PDFPlumberTableExtractor(config)
