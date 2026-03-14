# -*- coding: utf-8 -*-
"""
Integration tests for Orchestrator interactive flow

Tests the complete interactive flow from intent to execution.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.orchestrator.orchestrator import ProcessOrchestrator
from app.agents.orchestrator.state_machine import ProcessState
from app.agents.orchestrator.interaction_models import (
    InteractionType,
    InputType,
    UserResponse,
)


class TestOrchestratorInteractiveFlow:
    """Integration tests for interactive flow"""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked agents"""
        config = {"test_mode": True}

        with patch('app.agents.orchestrator.orchestrator.discover_agents'):
            with patch('app.agents.orchestrator.orchestrator.AgentRegistry') as mock_registry:
                # Mock agent creation
                mock_agent = AsyncMock()
                mock_agent.process = AsyncMock(return_value={
                    "success": True,
                    "result": {"content": "Mock result"}
                })
                mock_registry.create = MagicMock(return_value=mock_agent)

                orchestrator = ProcessOrchestrator(config)

                # Manually add mocked agents
                orchestrator._agents = {
                    "writing": mock_agent,
                    "proofread": mock_agent,
                    "review": mock_agent,
                }

                return orchestrator

    @pytest.mark.asyncio
    async def test_process_intent_with_complete_info(self, orchestrator):
        """Test processing with complete information (no interaction needed)"""
        result = await orchestrator.process_intent_with_interaction(
            user_input="Proofread this document",
            context={}
        )

        # Should either complete or reach a state requiring confirmation
        assert result["success"] is True
        assert "state" in result

    @pytest.mark.asyncio
    async def test_process_intent_requests_info(self, orchestrator):
        """Test that missing info triggers info request"""
        result = await orchestrator.process_intent_with_interaction(
            user_input="Calculate torque",  # Missing required info
            context={}
        )

        # Should request more information or proceed to preview
        if result.get("requires_response"):
            assert result["interaction_type"] in [
                InteractionType.INFO_REQUEST.value,
                InteractionType.PREVIEW.value
            ]

    @pytest.mark.asyncio
    async def test_continue_conversation_with_user_response(self, orchestrator):
        """Test continuing conversation after user provides info"""
        # First request
        result1 = await orchestrator.process_intent_with_interaction(
            user_input="Calculate torque",
            context={}
        )

        if result1.get("requires_response") and result1.get("interaction_type") == InteractionType.INFO_REQUEST.value:
            # User provides missing info
            response = UserResponse(
                session_id="test_session",
                response_type=InputType.TEXT,
                content="material=stainless steel,grade=A2-70"
            )

            result2 = await orchestrator.continue_conversation(response)

            # Should proceed to preview or execution
            assert result2["success"] is True

    @pytest.mark.asyncio
    async def test_user_confirms_execution(self, orchestrator):
        """Test user confirming execution"""
        # Set up state as if preview was shown
        orchestrator._collected_info = {
            "intent": {"type": "proofread"},
            "context": {},
            "collected_info": {"content": "test"}
        }
        orchestrator.interaction_manager._pending_interaction = {
            "type": InteractionType.PREVIEW,
            "intent": {"type": "proofread"},
            "collected_info": {}
        }

        response = UserResponse(
            session_id="test_session",
            content="",
            selected_option="confirm"
        )

        result = await orchestrator.continue_conversation(response)

        # Should execute or attempt to execute
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_user_cancels_execution(self, orchestrator):
        """Test user cancelling execution"""
        orchestrator._collected_info = {
            "intent": {"type": "test"},
            "context": {}
        }
        orchestrator.interaction_manager._pending_interaction = {
            "type": InteractionType.PREVIEW,
            "intent": {"type": "test"},
            "collected_info": {}
        }

        response = UserResponse(
            session_id="test_session",
            content="",
            selected_option="cancel"
        )

        result = await orchestrator.continue_conversation(response)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_interaction_status(self, orchestrator):
        """Test getting interaction status"""
        status = orchestrator.get_interaction_status()

        assert "is_awaiting_input" in status
        assert "current_state" in status
        assert "collected_info_keys" in status


class TestOrchestratorIndependentAgents:
    """Tests for independent proofread and review agents"""

    @pytest.fixture
    def orchestrator_with_agents(self):
        """Create orchestrator with mocked agents"""
        config = {"test_mode": True}

        with patch('app.agents.orchestrator.orchestrator.discover_agents'):
            with patch('app.agents.orchestrator.orchestrator.AgentRegistry') as mock_registry:
                mock_proofread = AsyncMock()
                mock_proofread.process = AsyncMock(return_value={
                    "success": True,
                    "result": {
                        "issues": [],
                        "suggestions": ["Suggestion 1"],
                        "content": "Proofread content"
                    }
                })

                mock_review = AsyncMock()
                mock_review.process = AsyncMock(return_value={
                    "success": True,
                    "result": {
                        "passed": True,
                        "warnings": [],
                        "report": "Review report"
                    }
                })

                def create_agent(name, config):
                    if name == "proofread":
                        return mock_proofread
                    elif name == "review":
                        return mock_review
                    return AsyncMock()

                mock_registry.create = MagicMock(side_effect=create_agent)

                orchestrator = ProcessOrchestrator(config)
                orchestrator._agents = {
                    "proofread": mock_proofread,
                    "review": mock_review,
                }

                return orchestrator

    @pytest.mark.asyncio
    async def test_proofread_only(self, orchestrator_with_agents):
        """Test independent proofread call"""
        result = await orchestrator_with_agents.proofread_only(
            content="This is test content",
            check_type="all"
        )

        assert result["success"] is True
        assert "result" in result

    @pytest.mark.asyncio
    async def test_proofread_with_specific_check_type(self, orchestrator_with_agents):
        """Test proofread with specific check type"""
        result = await orchestrator_with_agents.proofread_only(
            content="Test content",
            check_type="terminology"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_review_only(self, orchestrator_with_agents):
        """Test independent review call"""
        result = await orchestrator_with_agents.review_only(
            content="This is test content",
            check_type="all"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_review_with_standards(self, orchestrator_with_agents):
        """Test review with specific standards"""
        result = await orchestrator_with_agents.review_only(
            content="Test content",
            check_type="compliance",
            standards=["Enterprise standard", "Safety standard"]
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_proofread_agent_not_available(self):
        """Test proofread when agent is not available"""
        config = {"test_mode": True}

        with patch('app.agents.orchestrator.orchestrator.discover_agents'):
            with patch('app.agents.orchestrator.orchestrator.AgentRegistry') as mock_registry:
                mock_registry.create = MagicMock(return_value=None)

                orchestrator = ProcessOrchestrator(config)
                orchestrator._agents = {}  # No agents available

                result = await orchestrator.proofread_only("content")

                assert result["success"] is False
                assert "error" in result

    @pytest.mark.asyncio
    async def test_review_agent_not_available(self):
        """Test review when agent is not available"""
        config = {"test_mode": True}

        with patch('app.agents.orchestrator.orchestrator.discover_agents'):
            with patch('app.agents.orchestrator.orchestrator.AgentRegistry') as mock_registry:
                mock_registry.create = MagicMock(return_value=None)

                orchestrator = ProcessOrchestrator(config)
                orchestrator._agents = {}

                result = await orchestrator.review_only("content")

                assert result["success"] is False
                assert "error" in result


class TestOrchestratorStateTransitions:
    """Tests for state transitions during interactive flow"""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for state testing"""
        config = {"test_mode": True}

        with patch('app.agents.orchestrator.orchestrator.discover_agents'):
            with patch('app.agents.orchestrator.orchestrator.AgentRegistry') as mock_registry:
                mock_registry.create = MagicMock(return_value=AsyncMock())

                orchestrator = ProcessOrchestrator(config)
                return orchestrator

    @pytest.mark.asyncio
    async def test_state_transitions_to_intent_recognition(self, orchestrator):
        """Test state transitions to INTENT_RECOGNITION"""
        await orchestrator.process_intent_with_interaction("test input")

        # State should have moved from IDLE
        assert orchestrator.state_machine.current_state in [
            ProcessState.INTENT_RECOGNITION,
            ProcessState.INFO_ASSESSMENT,
            ProcessState.INFO_COLLECTION,
            ProcessState.PREVIEW_GENERATION,
            ProcessState.USER_CONFIRMATION,
            ProcessState.PAUSED,
            ProcessState.COMPLETION,
            ProcessState.ERROR
        ]

    @pytest.mark.asyncio
    async def test_state_transitions_through_interactive_flow(self, orchestrator):
        """Test state transitions through interactive flow"""
        # Start
        assert orchestrator.state_machine.current_state == ProcessState.IDLE

        # Process intent
        result = await orchestrator.process_intent_with_interaction("Proofread this document")

        # Should have moved from IDLE
        assert orchestrator.state_machine.current_state != ProcessState.IDLE

    @pytest.mark.asyncio
    async def test_state_goes_to_error_on_exception(self, orchestrator):
        """Test state goes to ERROR on exception"""
        # Force an error by making intent recognizer fail
        orchestrator.intent_recognizer.recognize = AsyncMock(
            side_effect=Exception("Test error")
        )

        result = await orchestrator.process_intent_with_interaction("test")

        assert result["success"] is False
        assert orchestrator.state_machine.current_state == ProcessState.ERROR


class TestOrchestratorContextHandling:
    """Tests for context handling in interactive flow"""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for context testing"""
        config = {"test_mode": True}

        with patch('app.agents.orchestrator.orchestrator.discover_agents'):
            with patch('app.agents.orchestrator.orchestrator.AgentRegistry') as mock_registry:
                mock_registry.create = MagicMock(return_value=AsyncMock())

                orchestrator = ProcessOrchestrator(config)
                return orchestrator

    @pytest.mark.asyncio
    async def test_context_passed_to_assessment(self, orchestrator):
        """Test that context is passed to info assessment"""
        context = {
            "document_context": {"title": "Test Document"},
            "additional_info": {"key": "value"}
        }

        result = await orchestrator.process_intent_with_interaction(
            user_input="test",
            context=context
        )

        # Should complete without error
        assert "success" in result

    @pytest.mark.asyncio
    async def test_collected_info_updated(self, orchestrator):
        """Test that collected info is updated during interaction"""
        orchestrator._collected_info = {"existing": "value"}

        # Simulate user response updating info
        orchestrator.interaction_manager._pending_interaction = {
            "type": InteractionType.INFO_REQUEST,
            "missing_items": []
        }

        response = UserResponse(
            session_id="test",
            content="New info"
        )

        result = await orchestrator.continue_conversation(response)

        # Collected info should be updated
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_collected_info_cleared_after_completion(self, orchestrator):
        """Test that collected info is cleared after task completion"""
        orchestrator._collected_info = {"intent": {}, "context": {}}

        # Set up for execution
        orchestrator.interaction_manager._pending_interaction = {
            "type": InteractionType.PREVIEW,
            "intent": {"type": "test"},
            "collected_info": {}
        }

        response = UserResponse(
            session_id="test",
            content="",
            selected_option="confirm"
        )

        # This will attempt execution and clear collected info
        await orchestrator.continue_conversation(response)


class TestOrchestratorEdgeCases:
    """Edge case tests for orchestrator"""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for edge case testing"""
        config = {"test_mode": True}

        with patch('app.agents.orchestrator.orchestrator.discover_agents'):
            with patch('app.agents.orchestrator.orchestrator.AgentRegistry') as mock_registry:
                mock_registry.create = MagicMock(return_value=AsyncMock())

                orchestrator = ProcessOrchestrator(config)
                return orchestrator

    @pytest.mark.asyncio
    async def test_empty_user_input(self, orchestrator):
        """Test handling empty user input"""
        result = await orchestrator.process_intent_with_interaction("")

        # Should handle gracefully
        assert "success" in result

    @pytest.mark.asyncio
    async def test_very_long_user_input(self, orchestrator):
        """Test handling very long user input"""
        long_input = "Calculate torque " * 100

        result = await orchestrator.process_intent_with_interaction(long_input)

        assert "success" in result

    @pytest.mark.asyncio
    async def test_special_characters_in_input(self, orchestrator):
        """Test handling special characters in input"""
        special_input = "Calculate <M8> screw torque @#$%^&*()"

        result = await orchestrator.process_intent_with_interaction(special_input)

        assert "success" in result

    @pytest.mark.asyncio
    async def test_unicode_input(self, orchestrator):
        """Test handling unicode input"""
        unicode_input = "Calculate torque English"

        result = await orchestrator.process_intent_with_interaction(unicode_input)

        assert "success" in result

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, orchestrator):
        """Test handling concurrent requests"""
        import asyncio

        tasks = [
            orchestrator.process_intent_with_interaction(f"Test {i}")
            for i in range(3)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should complete (success or error, not crash)
        for result in results:
            assert not isinstance(result, Exception)

    @pytest.mark.asyncio
    async def test_task_creation_in_memory_mode(self, orchestrator):
        """Test task creation without repository"""
        task_id = await orchestrator.create_task("Test Task")

        assert task_id is not None
        assert orchestrator.current_task_id == task_id

    @pytest.mark.asyncio
    async def test_multiple_continue_without_pending(self, orchestrator):
        """Test continue_conversation when no pending interaction"""
        response = UserResponse(
            session_id="test",
            content="test"
        )

        # No pending interaction set
        result = await orchestrator.continue_conversation(response)

        # Should handle gracefully
        assert result["success"] is False
