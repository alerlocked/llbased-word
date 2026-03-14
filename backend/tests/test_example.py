"""
测试示例文件
"""
import pytest


@pytest.mark.unit
def test_example_unit():
    """单元测试示例"""
    assert 1 + 1 == 2


@pytest.mark.integration
def test_example_integration():
    """集成测试示例"""
    result = "hello" + " " + "world"
    assert result == "hello world"


class TestExampleClass:
    """测试类示例"""

    @pytest.mark.unit
    def test_class_method(self):
        """类方法测试"""
        assert True

    @pytest.mark.unit
    def test_with_fixture(self, test_data_dir):
        """使用fixture的测试"""
        assert test_data_dir.exists()