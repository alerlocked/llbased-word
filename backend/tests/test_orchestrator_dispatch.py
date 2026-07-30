"""Tests for ProcessOrchestrator dispatch chain + shortcut protection.

Covers the 4th-step downstream fix (intent-llm-dispatch-fix):
- _dispatch_to_sub_agent: document_generation→writing, user_confirmation→noop
- process_intent: generation_mode shortcut bypasses LLM recognize (主链保护)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.orchestrator.orchestrator import ProcessOrchestrator


@pytest.fixture
def orchestrator():
    config = {"test_mode": True}
    with patch('app.agents.orchestrator.orchestrator.discover_agents'):
        with patch('app.agents.orchestrator.orchestrator.AgentRegistry') as mock_registry:
            mock_agent = AsyncMock()
            mock_agent.process = AsyncMock(return_value={
                "success": True, "result": {"content": "mock"}
            })
            mock_registry.create = MagicMock(return_value=mock_agent)
            orch = ProcessOrchestrator(config)
            orch._agents = {
                "writing": mock_agent, "review": mock_agent, "proofread": mock_agent,
            }
            return orch


class TestDispatchChainFix:
    """下游断链修复:document_generation→writing, user_confirmation→noop。"""

    @pytest.mark.asyncio
    async def test_document_generation_routes_to_writing(self, orchestrator):
        result = await orchestrator._dispatch_to_sub_agent(
            {"type": "document_generation", "content": "test"})
        assert result["agent"] == "writing"
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_user_confirmation_is_skipped(self, orchestrator):
        # 修复前:落 unknown;修复后:noop skipped(自动模式不交互)
        result = await orchestrator._dispatch_to_sub_agent({"type": "user_confirmation"})
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_legacy_pdf_parsing_pending(self, orchestrator):
        result = await orchestrator._dispatch_to_sub_agent({"type": "pdf_parsing"})
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_existing_review_mapping_intact(self, orchestrator):
        result = await orchestrator._dispatch_to_sub_agent({"type": "compliance_check"})
        assert result["agent"] == "review"

    @pytest.mark.asyncio
    async def test_existing_proofread_mapping_intact(self, orchestrator):
        result = await orchestrator._dispatch_to_sub_agent({"type": "terminology_alignment"})
        assert result["agent"] == "proofread"

    @pytest.mark.asyncio
    async def test_truly_unknown_type_still_unknown(self, orchestrator):
        result = await orchestrator._dispatch_to_sub_agent({"type": "totally_unknown_xyz"})
        assert result["status"] == "unknown"


class TestShortcutProtection:
    """generation_mode shortcut 不走 LLM recognize(generate/fill 主链保护)。"""

    @pytest.mark.asyncio
    async def test_generate_shortcut_skips_recognize(self, orchestrator):
        # recognize 不应被调(shortcut 直接 draft_complete)
        orchestrator.intent_recognizer.recognize = AsyncMock(
            return_value={"type": "should_not_be_called"})
        with patch.object(orchestrator, "_handle_draft_complete",
                          AsyncMock(return_value={"success": True})):
            await orchestrator.process_intent(
                user_input="生成", context={"generation_mode": "generate"})
        orchestrator.intent_recognizer.recognize.assert_not_called()

    @pytest.mark.asyncio
    async def test_fill_shortcut_skips_recognize(self, orchestrator):
        orchestrator.intent_recognizer.recognize = AsyncMock(
            return_value={"type": "should_not_be_called"})
        with patch.object(orchestrator, "_handle_draft_complete",
                          AsyncMock(return_value={"success": True})):
            await orchestrator.process_intent(
                user_input="补齐", context={"generation_mode": "fill"})
        orchestrator.intent_recognizer.recognize.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_shortcut_calls_recognize(self, orchestrator):
        # 非 shortcut 分支 → 调 LLM recognize
        orchestrator.intent_recognizer.recognize = AsyncMock(
            return_value={"type": "create_document", "confidence": 0.9})
        with patch.object(orchestrator, "task_decomposer") as mock_td, \
             patch.object(orchestrator, "_aggregate_results",
                          AsyncMock(return_value={"generated_content": "x"})):
            mock_td.decompose = AsyncMock(return_value=[])
            await orchestrator.process_intent(user_input="创建文件", context={})
        orchestrator.intent_recognizer.recognize.assert_called_once()
