"""
Tests for save_summary being wired into conversation flow.
Covers fix #4: cross-session memory actually gets saved.
"""
import pytest
from unittest.mock import patch, MagicMock
import tempfile
from pathlib import Path


class TestSaveSummaryWired:
    """save_summary must be called when saving conversation state."""

    def test_save_state_with_context_calls_save_summary(self):
        """When save_state_with_context_engineering runs, a memory file is created."""
        from app.services.conversation_service import ConversationService

        svc = ConversationService()
        session_id = "test-save-summary-001"
        state = {
            "user_input": "请写一段装配工艺卡",
            "conversation_history": [
                {"role": "user", "content": "请写一段装配工艺卡"},
                {"role": "assistant", "content": "好的，我来为您编写装配工艺卡引言"},
                {"role": "user", "content": "请增加扭矩参数"},
                {"role": "assistant", "content": "已添加扭矩参数 M12 螺栓拧紧力矩为 45±5 N·m"},
            ],
            "current_step": "writing",
        }

        # Mock DB
        mock_db = MagicMock()

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(svc, "save_state", return_value=True):
                with patch("app.services.conversation_service.settings") as mock_settings:
                    mock_settings.DATA_DIR = Path(tmp)
                    # Run the method
                    result = svc.save_state_with_context_engineering(
                        mock_db, session_id, state
                    )

            assert result is True

            # Verify memory file was created
            memory_dir = Path(tmp) / "memory"
            memory_file = memory_dir / f"{session_id}.md"
            assert memory_file.exists(), "Memory file should be created"

            content = memory_file.read_text(encoding="utf-8")
            assert "# 会话摘要" in content
            assert "装配工艺卡" in content

    def test_save_summary_with_empty_history(self):
        """Empty conversation history should not create a memory file."""
        from app.services.conversation_service import ConversationService

        svc = ConversationService()
        session_id = "test-save-empty-001"
        state = {
            "user_input": "hello",
            "conversation_history": [],
            "current_step": "idle",
        }

        mock_db = MagicMock()

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(svc, "save_state", return_value=True):
                with patch("app.services.conversation_service.settings") as mock_settings:
                    mock_settings.DATA_DIR = Path(tmp)
                    result = svc.save_state_with_context_engineering(
                        mock_db, session_id, state
                    )

            assert result is True

            memory_dir = Path(tmp) / "memory"
            # No memory file should be created for empty history
            md_files = list(memory_dir.glob("*.md")) if memory_dir.exists() else []
            assert len(md_files) == 0, "No memory file for empty history"
