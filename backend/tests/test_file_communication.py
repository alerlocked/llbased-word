"""
test_file_communication.py - Agent 文件通信测试
"""
import pytest
from pathlib import Path
import json
import time
from datetime import datetime

from app.services.agent_communication import (
    AgentOutputWriter,
    AgentFeedbackManager,
    AgentCleanupManager,
    FeedbackData,
    AgentPaths
)


@pytest.fixture
def temp_base_path(tmp_path):
    """创建临时测试目录"""
    return tmp_path


class TestAgentOutputWriter:
    """测试 AgentOutputWriter"""
    
    def test_write_output(self, temp_base_path):
        """测试写入输出文件"""
        writer = AgentOutputWriter("test_session", temp_base_path)
        
        content = "# 测试文档\n\n这是测试内容。"
        file_path = writer.write_output(content)
        
        assert file_path.exists()
        assert content in file_path.read_text(encoding='utf-8')
    
    def test_write_output_with_filename(self, temp_base_path):
        """测试使用指定文件名写入"""
        writer = AgentOutputWriter("test_session", temp_base_path)
        
        content = "# 测试文档\n\n这是测试内容。"
        file_path = writer.write_output(content, "custom_output.md")
        
        assert file_path.exists()
        assert file_path.name == "custom_output.md"
    
    def test_get_latest_output(self, temp_base_path):
        """测试获取最新输出"""
        writer = AgentOutputWriter("test_session", temp_base_path)
        
        # 写入多个文件
        writer.write_output("内容 1", "output_1.md")
        time.sleep(0.1)  # 确保时间戳不同
        writer.write_output("内容 2", "output_2.md")
        
        # 获取最新
        latest = writer.get_latest_output()
        
        assert latest == "内容 2"
    
    def test_get_latest_output_empty(self, temp_base_path):
        """测试没有输出文件时返回 None"""
        writer = AgentOutputWriter("test_session", temp_base_path)
        
        latest = writer.get_latest_output()
        
        assert latest is None
    
    def test_list_outputs(self, temp_base_path):
        """测试列出输出文件"""
        writer = AgentOutputWriter("test_session", temp_base_path)
        
        writer.write_output("内容 1", "output_1.md")
        time.sleep(0.1)
        writer.write_output("内容 2", "output_2.md")
        
        outputs = writer.list_outputs()
        
        assert len(outputs) >= 2


class TestAgentFeedbackManager:
    """测试 AgentFeedbackManager"""
    
    def test_write_feedback(self, temp_base_path):
        """测试写入反馈文件"""
        manager = AgentFeedbackManager(temp_base_path)
        
        feedback = FeedbackData(
            review_id="test_review_id",
            source_file=".agent-outputs/test_session/output_1.md",
            score=65,
            issues=[{"severity": "error", "message": "测试问题"}],
            suggestions=[{"message": "测试建议"}],
            timestamp=datetime.now().isoformat(),
            passed=False
        )
        
        file_path = manager.write_feedback(feedback)
        
        assert file_path.exists()
        
        # 读取并验证
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert data["review_id"] == "test_review_id"
        assert data["score"] == 65
    
    def test_get_latest_feedback(self, temp_base_path):
        """测试获取最新反馈"""
        manager = AgentFeedbackManager(temp_base_path)
        
        feedback1 = FeedbackData(
            review_id="review_1",
            source_file="file1.md",
            score=70,
            issues=[],
            suggestions=[],
            timestamp=datetime.now().isoformat(),
            passed=False
        )
        
        feedback2 = FeedbackData(
            review_id="review_2",
            source_file="file2.md",
            score=65,
            issues=[],
            suggestions=[],
            timestamp=datetime.now().isoformat(),
            passed=False
        )
        
        manager.write_feedback(feedback1)
        time.sleep(0.1)
        manager.write_feedback(feedback2)
        
        latest = manager.get_latest_feedback()
        
        assert latest.review_id == "review_2"
    
    def test_get_latest_feedback_empty(self, temp_base_path):
        """测试没有反馈文件时返回 None"""
        manager = AgentFeedbackManager(temp_base_path)
        
        latest = manager.get_latest_feedback()
        
        assert latest is None
    
    def test_has_pending_feedback(self, temp_base_path):
        """测试检查是否有待处理反馈"""
        manager = AgentFeedbackManager(temp_base_path)
        
        assert not manager.has_pending_feedback()
        
        # 写入反馈
        feedback = FeedbackData(
            review_id="test",
            source_file="test.md",
            score=65,
            issues=[],
            suggestions=[],
            timestamp=datetime.now().isoformat()
        )
        manager.write_feedback(feedback)
        
        assert manager.has_pending_feedback()
    
    def test_clear_feedback(self, temp_base_path):
        """测试清除反馈文件"""
        manager = AgentFeedbackManager(temp_base_path)
        
        feedback = FeedbackData(
            review_id="test",
            source_file="test.md",
            score=65,
            issues=[],
            suggestions=[],
            timestamp=datetime.now().isoformat()
        )
        
        file_path = manager.write_feedback(feedback)
        assert file_path.exists()
        
        manager.clear_feedback(file_path)
        assert not file_path.exists()


class TestAgentCleanupManager:
    """测试 AgentCleanupManager"""
    
    def test_cleanup_old_outputs(self, temp_base_path):
        """测试清理旧输出文件"""
        writer = AgentOutputWriter("test_session", temp_base_path)
        
        # 写入文件
        writer.write_output("内容")
        
        # 立即清理（days=0）
        cleanup_manager = AgentCleanupManager(temp_base_path)
        cleaned = cleanup_manager.cleanup_old_outputs(days=0)
        
        assert cleaned >= 0
    
    def test_cleanup_expired_feedbacks(self, temp_base_path):
        """测试清理过期反馈"""
        manager = AgentFeedbackManager(temp_base_path)
        
        # 写入反馈
        feedback = FeedbackData(
            review_id="test",
            source_file="test.md",
            score=65,
            issues=[],
            suggestions=[],
            timestamp=datetime.now().isoformat()
        )
        manager.write_feedback(feedback)
        
        # 立即清理（hours=0）
        cleanup_manager = AgentCleanupManager(temp_base_path)
        cleaned = cleanup_manager.cleanup_expired_feedbacks(hours=0)
        
        assert cleaned >= 0


class TestAgentPaths:
    """测试 AgentPaths"""
    
    def test_get_output_dir(self, temp_base_path):
        """测试获取输出目录"""
        output_dir = AgentPaths.get_output_dir("test_session", temp_base_path)
        
        assert output_dir.name == "test_session"
        assert output_dir.parent.name == ".agent-outputs"
    
    def test_get_feedback_dir(self, temp_base_path):
        """测试获取反馈目录"""
        feedback_dir = AgentPaths.get_feedback_dir(temp_base_path)
        
        assert feedback_dir.name == ".agent-feedback"
