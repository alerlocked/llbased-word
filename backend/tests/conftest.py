"""
测试配置文件
"""
import os
import sys
import pytest
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 测试配置
@pytest.fixture(scope="session")
def test_data_dir():
    """测试数据目录"""
    return project_root.parent / "test_data"

@pytest.fixture(scope="session")
def module_dir():
    """模块目录"""
    return project_root.parent / "module"

@pytest.fixture(autouse=True)
def setup_test_environment():
    """设置测试环境"""
    # 设置测试环境变量
    os.environ["TESTING"] = "true"

    # 保存原始环境变量
    original_env = os.environ.copy()

    yield

    # 恢复环境变量
    os.environ.clear()
    os.environ.update(original_env)