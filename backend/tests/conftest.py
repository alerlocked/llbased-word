"""
conftest.py - pytest 配置
"""
import pytest
from pathlib import Path
import tempfile


@pytest.fixture
def tmp_path():
    """临时目录 fixture"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def project_root():
    """项目根目录"""
    return Path(__file__).parent.parent.parent.parent
