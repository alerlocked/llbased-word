"""
路径处理工具函数
提供路径规范化、静态URL构建等通用功能
"""
from typing import Union
from pathlib import Path


def normalize_path(path: Union[str, Path]) -> str:
    """
    规范化路径（将反斜杠替换为正斜杠）
    
    Args:
        path: 原始路径
    
    Returns:
        规范化后的路径字符串
    """
    if isinstance(path, Path):
        path = str(path)
    return path.replace('\\', '/')


def build_static_url(relative_path: Union[str, Path], base_path: str = "/static/data") -> str:
    """
    构建静态文件URL
    
    Args:
        relative_path: 相对于DATA_DIR的路径
        base_path: 基础路径，默认为"/static/data"
    
    Returns:
        完整的静态URL路径
    """
    normalized_path = normalize_path(relative_path)
    
    # 如果路径已经包含data/，直接使用；否则添加data/
    if normalized_path.startswith('data/'):
        return f"{base_path.replace('/data', '')}/{normalized_path}"
    else:
        return f"{base_path}/{normalized_path}"


def ensure_path_normalized(path: Union[str, Path]) -> str:
    """
    确保路径已规范化（兼容函数，与normalize_path相同）
    
    Args:
        path: 原始路径
    
    Returns:
        规范化后的路径字符串
    """
    return normalize_path(path)

