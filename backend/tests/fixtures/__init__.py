"""
tests/fixtures/__init__.py - Fixtures 加载工具
"""
import yaml
from pathlib import Path
from typing import Dict, Any


FIXTURES_DIR = Path(__file__).parent


def load_fixture(name: str) -> str:
    """
    加载测试 fixture
    
    Args:
        name: fixture 名称（不含 .yaml 后缀）
        
    Returns:
        fixture 内容字符串
    """
    fixture_path = FIXTURES_DIR / f"{name}.yaml"
    
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {name}")
    
    with open(fixture_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    return data.get("content", "")
