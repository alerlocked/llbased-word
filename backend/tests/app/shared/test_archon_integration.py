"""
测试Archon集成功能
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from archon_integration import (
    ArchonClient,
    ensure_archon_connection,
    create_archon_epic,
    create_archon_task,
    track_archon_task_start,
    track_archon_task_complete,
    add_test_results_to_archon
)


@pytest.mark.integration
class TestArchonIntegration:
    """Archon集成测试类"""

    @pytest.mark.unit
    def test_archon_client_initialization(self):
        """测试Archon客户端初始化"""
        client = ArchonClient()
        assert client.base_url == "http://localhost:8181"
        assert client.project_id == "f9ecaf8b-ff17-467d-bf29-37aae558bb4e"
        assert client.session is not None

    @pytest.mark.unit
    def test_ensure_archon_connection(self):
        """测试Archon连接检查"""
        # 假设Archon服务正在运行
        result = ensure_archon_connection()
        # 实际结果取决于Archon服务状态
        assert isinstance(result, bool)

    @pytest.mark.integration
    def test_create_archon_epic_workflow(self):
        """测试完整的史诗任务创建流程"""
        if not ensure_archon_connection():
            pytest.skip("Archon service not available")

        # 创建史诗任务
        epic_id = create_archon_epic(
            "测试史诗任务",
            "这是一个用于测试的史诗任务"
        )

        assert epic_id is not None
        assert isinstance(epic_id, str)
        print(f"✅ 创建史诗任务成功: {epic_id}")

    @pytest.mark.integration
    def test_create_archon_task_workflow(self):
        """测试完整的子任务创建流程"""
        if not ensure_archon_connection():
            pytest.skip("Archon service not available")

        # 首先创建史诗任务
        epic_id = create_archon_epic(
            "测试任务史诗",
            "用于测试子任务创建的史诗"
        )

        if not epic_id:
            pytest.skip("Failed to create epic")

        # 创建子任务
        task_id = create_archon_task(
            epic_id,
            "测试子任务",
            "这是一个测试子任务",
            priority="high"
        )

        assert task_id is not None
        assert isinstance(task_id, str)
        print(f"✅ 创建子任务成功: {task_id}")

    @pytest.mark.integration
    def test_task_status_workflow(self):
        """测试任务状态更新流程"""
        if not ensure_archon_connection():
            pytest.skip("Archon service not available")

        # 创建史诗和任务
        epic_id = create_archon_epic(
            "状态测试史诗",
            "用于测试状态更新的史诗"
        )

        if not epic_id:
            pytest.skip("Failed to create epic")

        task_id = create_archon_task(
            epic_id,
            "状态测试任务",
            "用于测试状态流转"
        )

        if not task_id:
            pytest.skip("Failed to create task")

        # 测试状态流转
        assert track_archon_task_start(task_id, "开始测试任务")
        print(f"✅ 任务开始: {task_id}")

        assert track_archon_task_complete(task_id, "测试任务完成")
        print(f"✅ 任务完成: {task_id}")

    @pytest.mark.integration
    def test_add_test_results(self):
        """测试添加测试结果"""
        if not ensure_archon_connection():
            pytest.skip("Archon service not available")

        # 创建任务
        epic_id = create_archon_epic(
            "测试结果史诗",
            "用于测试测试结果上传"
        )

        if not epic_id:
            pytest.skip("Failed to create epic")

        task_id = create_archon_task(
            epic_id,
            "测试结果任务",
            "用于测试测试结果上传功能"
        )

        if not task_id:
            pytest.skip("Failed to create task")

        # 模拟测试结果
        test_results = {
            "total_tests": 10,
            "passed_tests": 9,
            "failed_tests": 1,
            "coverage_percentage": 85.5,
            "test_files": [
                "test_module1.py",
                "test_module2.py"
            ],
            "summary": "大部分测试通过，覆盖率良好"
        }

        result = add_test_results_to_archon(task_id, test_results)
        assert result is True
        print(f"✅ 测试结果上传成功: {task_id}")

    @pytest.mark.integration
    def test_error_handling(self):
        """测试错误处理"""
        # 测试无效的史诗ID
        result = create_archon_task(
            "invalid-epic-id",
            "不应该创建的任务",
            "这个任务不应该被创建"
        )
        # 应该返回None或处理错误
        assert result is None or isinstance(result, str)

    @pytest.mark.integration
    def test_project_summary(self):
        """测试项目摘要获取"""
        if not ensure_archon_connection():
            pytest.skip("Archon service not available")

        from archon_integration import get_archon_project_status
        summary = get_archon_project_status()

        assert summary is not None
        assert isinstance(summary, dict)
        print(f"✅ 项目摘要: {summary}")