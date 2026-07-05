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


@pytest.fixture(autouse=True)
def _cleanup_global_state():
    """Stop lingering patches + GC after each test to prevent cross-test
    pollution (AsyncMock residue leaking into other modules' DB sessions,
    which caused draft_service flakiness under full-suite runs).
    """
    yield
    from unittest import mock
    try:
        mock.patch.stopall()
    except Exception:
        pass
    import gc
    gc.collect()
