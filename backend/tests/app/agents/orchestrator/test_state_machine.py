# -*- coding: utf-8 -*-
"""
Unit tests for state_machine module

Tests the process state machine with new interactive states.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.agents.orchestrator.state_machine import (
    ProcessState,
    StateTransition,
    ProcessStateMachine,
)


class TestProcessState:
    """Tests for ProcessState enum"""

    def test_all_states_defined(self):
        """Test all states are defined"""
        assert ProcessState.IDLE.value == "idle"
        assert ProcessState.INTENT_RECOGNITION.value == "intent_recognition"
        assert ProcessState.INFO_ASSESSMENT.value == "info_assessment"
        assert ProcessState.INFO_COLLECTION.value == "info_collection"
        assert ProcessState.PREVIEW_GENERATION.value == "preview_generation"
        assert ProcessState.USER_CONFIRMATION.value == "user_confirmation"
        assert ProcessState.TASK_DECOMPOSITION.value == "task_decomposition"
        assert ProcessState.TASK_EXECUTION.value == "task_execution"
        assert ProcessState.RESULT_AGGREGATION.value == "result_aggregation"
        assert ProcessState.USER_REVIEW.value == "user_review"
        assert ProcessState.COMPLETION.value == "completion"
        assert ProcessState.ERROR.value == "error"
        assert ProcessState.PAUSED.value == "paused"

    def test_new_interactive_states(self):
        """Test new interactive states are defined"""
        new_states = [
            ProcessState.INFO_ASSESSMENT,
            ProcessState.INFO_COLLECTION,
            ProcessState.PREVIEW_GENERATION,
            ProcessState.USER_CONFIRMATION,
            ProcessState.PAUSED,
        ]

        for state in new_states:
            assert isinstance(state, ProcessState)


class TestStateTransition:
    """Tests for StateTransition dataclass"""

    def test_state_transition_creation(self):
        """Test creating a state transition"""
        transition = StateTransition(
            from_state=ProcessState.IDLE,
            to_state=ProcessState.INTENT_RECOGNITION,
            condition="user_input"
        )

        assert transition.from_state == ProcessState.IDLE
        assert transition.to_state == ProcessState.INTENT_RECOGNITION
        assert transition.condition == "user_input"

    def test_state_transition_without_condition(self):
        """Test creating transition without condition"""
        transition = StateTransition(
            from_state=ProcessState.IDLE,
            to_state=ProcessState.INTENT_RECOGNITION
        )

        assert transition.condition is None


class TestProcessStateMachine:
    """Tests for ProcessStateMachine class"""

    @pytest.fixture
    def state_machine(self):
        """Create a state machine instance"""
        return ProcessStateMachine()

    def test_initialization(self, state_machine):
        """Test state machine initialization"""
        assert state_machine.current_state == ProcessState.IDLE
        assert len(state_machine.state_history) == 1
        assert state_machine.context == {}

    def test_initialization_with_repository(self):
        """Test initialization with repository"""
        mock_repo = MagicMock()
        mock_repo.get_state.return_value = None

        sm = ProcessStateMachine(repository=mock_repo, task_id="test_task")

        assert sm.repository == mock_repo
        assert sm.task_id == "test_task"

    def test_get_current_state(self, state_machine):
        """Test getting current state"""
        state = state_machine.get_current_state()

        assert state == ProcessState.IDLE

    def test_get_context(self, state_machine):
        """Test getting context"""
        state_machine.context = {"key": "value"}

        result = state_machine.get_context()

        assert result == {"key": "value"}
        # Should return a copy
        result["new_key"] = "new_value"
        assert "new_key" not in state_machine.context

    def test_update_context(self, state_machine):
        """Test updating context"""
        state_machine.update_context({"key1": "value1"})

        assert state_machine.context["key1"] == "value1"

        state_machine.update_context({"key2": "value2"})
        assert state_machine.context["key2"] == "value2"
        assert state_machine.context["key1"] == "value1"

    @pytest.mark.asyncio
    async def test_valid_transition(self, state_machine):
        """Test valid state transition"""
        result = await state_machine.transition_to(
            ProcessState.INTENT_RECOGNITION,
            trigger="user_input"
        )

        assert result is True
        assert state_machine.current_state == ProcessState.INTENT_RECOGNITION
        assert len(state_machine.state_history) == 2

    @pytest.mark.asyncio
    async def test_invalid_transition(self, state_machine):
        """Test invalid state transition"""
        # Try to go from IDLE directly to COMPLETION (invalid)
        result = await state_machine.transition_to(ProcessState.COMPLETION)

        assert result is False
        assert state_machine.current_state == ProcessState.IDLE

    @pytest.mark.asyncio
    async def test_transition_with_context_update(self, state_machine):
        """Test transition with context update"""
        await state_machine.transition_to(
            ProcessState.INTENT_RECOGNITION,
            context_update={"user_input": "test"},
            trigger="test"
        )

        assert state_machine.context["user_input"] == "test"

    @pytest.mark.asyncio
    async def test_transition_with_string_state(self, state_machine):
        """Test transition using string state value"""
        result = await state_machine.transition_to("intent_recognition")

        assert result is True
        assert state_machine.current_state == ProcessState.INTENT_RECOGNITION

    @pytest.mark.asyncio
    async def test_reset(self, state_machine):
        """Test resetting state machine"""
        await state_machine.transition_to(ProcessState.INTENT_RECOGNITION)
        state_machine.context = {"key": "value"}

        await state_machine.reset()

        assert state_machine.current_state == ProcessState.IDLE
        assert len(state_machine.context) == 0
        assert len(state_machine.state_history) == 1

    def test_can_transition_to_valid(self, state_machine):
        """Test checking valid transition possibility"""
        assert state_machine.can_transition_to(ProcessState.INTENT_RECOGNITION) is True
        assert state_machine.can_transition_to(ProcessState.ERROR) is True

    def test_can_transition_to_invalid(self, state_machine):
        """Test checking invalid transition possibility"""
        assert state_machine.can_transition_to(ProcessState.COMPLETION) is False
        assert state_machine.can_transition_to(ProcessState.TASK_EXECUTION) is False

    def test_get_available_transitions(self, state_machine):
        """Test getting available transitions"""
        available = state_machine.get_available_transitions()

        assert ProcessState.INTENT_RECOGNITION in available
        assert ProcessState.ERROR in available
        assert ProcessState.COMPLETION not in available

    def test_get_state_history(self, state_machine):
        """Test getting state history"""
        # Initial history has one entry
        history = state_machine.get_state_history()
        assert len(history) == 1

        # Add more transitions
        state_machine.state_history.append({"state": "new_state"})

        history = state_machine.get_state_history(limit=1)
        assert len(history) == 1

    def test_get_state_summary(self, state_machine):
        """Test getting state summary"""
        summary = state_machine.get_state_summary()

        assert "current_state" in summary
        assert "context_keys" in summary
        assert "history_count" in summary
        assert "available_transitions" in summary

    def test_set_task(self, state_machine):
        """Test setting task ID"""
        state_machine.set_task("task_123")

        assert state_machine.task_id == "task_123"


class TestInteractiveFlowTransitions:
    """Tests for new interactive flow state transitions"""

    @pytest.fixture
    def state_machine(self):
        return ProcessStateMachine()

    @pytest.mark.asyncio
    async def test_idle_to_intent_recognition(self, state_machine):
        """Test IDLE -> INTENT_RECOGNITION transition"""
        result = await state_machine.transition_to(ProcessState.INTENT_RECOGNITION)
        assert result is True

    @pytest.mark.asyncio
    async def test_intent_recognition_to_info_assessment(self, state_machine):
        """Test INTENT_RECOGNITION -> INFO_ASSESSMENT transition"""
        await state_machine.transition_to(ProcessState.INTENT_RECOGNITION)
        result = await state_machine.transition_to(ProcessState.INFO_ASSESSMENT)
        assert result is True

    @pytest.mark.asyncio
    async def test_info_assessment_to_info_collection(self, state_machine):
        """Test INFO_ASSESSMENT -> INFO_COLLECTION transition"""
        await state_machine.transition_to(ProcessState.INTENT_RECOGNITION)
        await state_machine.transition_to(ProcessState.INFO_ASSESSMENT)
        result = await state_machine.transition_to(ProcessState.INFO_COLLECTION)
        assert result is True

    @pytest.mark.asyncio
    async def test_info_assessment_to_preview_generation(self, state_machine):
        """Test INFO_ASSESSMENT -> PREVIEW_GENERATION transition"""
        await state_machine.transition_to(ProcessState.INTENT_RECOGNITION)
        await state_machine.transition_to(ProcessState.INFO_ASSESSMENT)
        result = await state_machine.transition_to(ProcessState.PREVIEW_GENERATION)
        assert result is True

    @pytest.mark.asyncio
    async def test_info_collection_to_paused(self, state_machine):
        """Test INFO_COLLECTION -> PAUSED transition"""
        await state_machine.transition_to(ProcessState.INTENT_RECOGNITION)
        await state_machine.transition_to(ProcessState.INFO_ASSESSMENT)
        await state_machine.transition_to(ProcessState.INFO_COLLECTION)
        result = await state_machine.transition_to(ProcessState.PAUSED)
        assert result is True

    @pytest.mark.asyncio
    async def test_paused_to_info_collection(self, state_machine):
        """Test PAUSED -> INFO_COLLECTION transition"""
        # Set up state
        state_machine.current_state = ProcessState.PAUSED

        result = await state_machine.transition_to(ProcessState.INFO_COLLECTION)
        assert result is True

    @pytest.mark.asyncio
    async def test_preview_generation_to_user_confirmation(self, state_machine):
        """Test PREVIEW_GENERATION -> USER_CONFIRMATION transition"""
        state_machine.current_state = ProcessState.PREVIEW_GENERATION

        result = await state_machine.transition_to(ProcessState.USER_CONFIRMATION)
        assert result is True

    @pytest.mark.asyncio
    async def test_user_confirmation_to_paused(self, state_machine):
        """Test USER_CONFIRMATION -> PAUSED transition"""
        state_machine.current_state = ProcessState.USER_CONFIRMATION

        result = await state_machine.transition_to(ProcessState.PAUSED)
        assert result is True

    @pytest.mark.asyncio
    async def test_user_confirmation_to_task_decomposition(self, state_machine):
        """Test USER_CONFIRMATION -> TASK_DECOMPOSITION transition"""
        state_machine.current_state = ProcessState.USER_CONFIRMATION

        result = await state_machine.transition_to(ProcessState.TASK_DECOMPOSITION)
        assert result is True

    @pytest.mark.asyncio
    async def test_user_confirmation_to_info_collection(self, state_machine):
        """Test USER_CONFIRMATION -> INFO_COLLECTION (modify) transition"""
        state_machine.current_state = ProcessState.USER_CONFIRMATION

        result = await state_machine.transition_to(ProcessState.INFO_COLLECTION)
        assert result is True

    @pytest.mark.asyncio
    async def test_paused_to_idle(self, state_machine):
        """Test PAUSED -> IDLE (cancel) transition"""
        state_machine.current_state = ProcessState.PAUSED

        result = await state_machine.transition_to(ProcessState.IDLE)
        assert result is True

    @pytest.mark.asyncio
    async def test_full_interactive_flow(self, state_machine):
        """Test complete interactive flow"""
        # IDLE -> INTENT_RECOGNITION
        await state_machine.transition_to(ProcessState.INTENT_RECOGNITION)

        # INTENT_RECOGNITION -> INFO_ASSESSMENT
        await state_machine.transition_to(ProcessState.INFO_ASSESSMENT)

        # INFO_ASSESSMENT -> INFO_COLLECTION (missing info)
        await state_machine.transition_to(ProcessState.INFO_COLLECTION)

        # INFO_COLLECTION -> PAUSED (waiting for user)
        await state_machine.transition_to(ProcessState.PAUSED)

        # PAUSED -> INFO_COLLECTION (user provided info)
        await state_machine.transition_to(ProcessState.INFO_COLLECTION)

        # INFO_COLLECTION -> PREVIEW_GENERATION
        await state_machine.transition_to(ProcessState.PREVIEW_GENERATION)

        # PREVIEW_GENERATION -> USER_CONFIRMATION
        await state_machine.transition_to(ProcessState.USER_CONFIRMATION)

        # USER_CONFIRMATION -> PAUSED (waiting for confirm)
        await state_machine.transition_to(ProcessState.PAUSED)

        # PAUSED -> USER_CONFIRMATION (user responded)
        await state_machine.transition_to(ProcessState.USER_CONFIRMATION)

        # USER_CONFIRMATION -> TASK_DECOMPOSITION (confirmed)
        await state_machine.transition_to(ProcessState.TASK_DECOMPOSITION)

        # Continue with normal flow
        await state_machine.transition_to(ProcessState.TASK_EXECUTION)
        await state_machine.transition_to(ProcessState.RESULT_AGGREGATION)
        await state_machine.transition_to(ProcessState.USER_REVIEW)
        await state_machine.transition_to(ProcessState.COMPLETION)

        assert state_machine.current_state == ProcessState.COMPLETION


class TestLegacyFlowTransitions:
    """Tests for legacy (non-interactive) flow transitions"""

    @pytest.fixture
    def state_machine(self):
        return ProcessStateMachine()

    @pytest.mark.asyncio
    async def test_skip_interactive_flow(self, state_machine):
        """Test skipping interactive states when info is complete"""
        # IDLE -> INTENT_RECOGNITION
        await state_machine.transition_to(ProcessState.INTENT_RECOGNITION)

        # Can go directly to TASK_DECOMPOSITION (skip interactive)
        result = await state_machine.transition_to(ProcessState.TASK_DECOMPOSITION)
        assert result is True

    @pytest.mark.asyncio
    async def test_info_assessment_to_task_decomposition(self, state_machine):
        """Test INFO_ASSESSMENT -> TASK_DECOMPOSITION (skip preview)"""
        await state_machine.transition_to(ProcessState.INTENT_RECOGNITION)
        await state_machine.transition_to(ProcessState.INFO_ASSESSMENT)

        result = await state_machine.transition_to(ProcessState.TASK_DECOMPOSITION)
        assert result is True


class TestErrorTransitions:
    """Tests for error state transitions"""

    @pytest.fixture
    def state_machine(self):
        return ProcessStateMachine()

    @pytest.mark.asyncio
    async def test_error_from_any_state(self, state_machine):
        """Test ERROR can be reached from various states"""
        states_to_test = [
            ProcessState.IDLE,
            ProcessState.INTENT_RECOGNITION,
            ProcessState.INFO_ASSESSMENT,
            ProcessState.INFO_COLLECTION,
            ProcessState.PREVIEW_GENERATION,
            ProcessState.USER_CONFIRMATION,
            ProcessState.PAUSED,
            ProcessState.TASK_EXECUTION,
        ]

        for state in states_to_test:
            sm = ProcessStateMachine()
            sm.current_state = state
            result = await sm.transition_to(ProcessState.ERROR)
            assert result is True, f"Failed to transition from {state} to ERROR"

    @pytest.mark.asyncio
    async def test_error_to_idle(self, state_machine):
        """Test ERROR -> IDLE transition"""
        state_machine.current_state = ProcessState.ERROR

        result = await state_machine.transition_to(ProcessState.IDLE)
        assert result is True


class TestValidTransitionsList:
    """Tests for VALID_TRANSITIONS list"""

    def test_contains_new_interactive_transitions(self):
        """Test that new interactive transitions are defined"""
        new_transitions = [
            (ProcessState.INTENT_RECOGNITION, ProcessState.INFO_ASSESSMENT),
            (ProcessState.INFO_ASSESSMENT, ProcessState.INFO_COLLECTION),
            (ProcessState.INFO_ASSESSMENT, ProcessState.PREVIEW_GENERATION),
            (ProcessState.INFO_COLLECTION, ProcessState.PAUSED),
            (ProcessState.PAUSED, ProcessState.INFO_COLLECTION),
            (ProcessState.INFO_COLLECTION, ProcessState.PREVIEW_GENERATION),
            (ProcessState.PREVIEW_GENERATION, ProcessState.USER_CONFIRMATION),
            (ProcessState.USER_CONFIRMATION, ProcessState.PAUSED),
            (ProcessState.PAUSED, ProcessState.USER_CONFIRMATION),
            (ProcessState.USER_CONFIRMATION, ProcessState.TASK_DECOMPOSITION),
            (ProcessState.USER_CONFIRMATION, ProcessState.INFO_COLLECTION),
        ]

        transition_set = {(t.from_state, t.to_state) for t in ProcessStateMachine.VALID_TRANSITIONS}

        for from_state, to_state in new_transitions:
            assert (from_state, to_state) in transition_set, \
                f"Missing transition: {from_state} -> {to_state}"

    def test_contains_legacy_transitions(self):
        """Test that legacy transitions still exist"""
        legacy_transitions = [
            (ProcessState.INTENT_RECOGNITION, ProcessState.TASK_DECOMPOSITION),
            (ProcessState.INFO_ASSESSMENT, ProcessState.TASK_DECOMPOSITION),
        ]

        transition_set = {(t.from_state, t.to_state) for t in ProcessStateMachine.VALID_TRANSITIONS}

        for from_state, to_state in legacy_transitions:
            assert (from_state, to_state) in transition_set
