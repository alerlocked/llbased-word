"""
文件处理工具函数
提供文件哈希计算等通用功能
"""
import hashlib
from typing import Union
from pathlib import Path

from app.shared.logging import get_logger
logger = get_logger(__name__)


def calculate_file_hash(file_content: bytes) -> str:
    """
    计算文件MD5哈希值
    
    Args:
        file_content: 文件内容（字节）
    
    Returns:
        MD5哈希值（十六进制字符串）
    """
    return hashlib.md5(file_content).hexdigest()


def calculate_file_hash_from_path(file_path: Union[str, Path]) -> str:
    """
    从文件路径计算MD5哈希值
    
    Args:
        file_path: 文件路径
    
    Returns:
        MD5哈希值（十六进制字符串）
    """
    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()
        return calculate_file_hash(file_content)
    except Exception as e:
        logger.error(f"❌ 计算文件哈希失败: {str(e)}")
        raise

