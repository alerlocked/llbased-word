# -*- coding: utf-8 -*-
"""
Unit tests for interaction_manager module

Tests the user interaction flow management.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.orchestrator.interaction_manager import InteractionManager
from app.agents.orchestrator.interaction_models import (
    InteractionType,
    InputType,
    InfoRequestMessage,
    PreviewMessage,
    ConfirmationMessage,
    UserResponse,
    MissingInfoItem,
)


class TestInteractionManagerInit:
    """Tests for InteractionManager initialization"""

    def test_init_default(self):
        """Test default initialization"""
        manager = InteractionManager()

        assert manager.repository is None
        assert manager.dialog_manager is None
        assert manager._pending_interaction is None

    def test_init_with_dependencies(self):
        """Test initialization with dependencies"""
        mock_repo = MagicMock()
        mock_dialog = MagicMock()

        manager = InteractionManager(
            repository=mock_repo,
            dialog_manager=mock_dialog
        )

        assert manager.repository == mock_repo
        assert manager.dialog_manager == mock_dialog


class TestRequestMissingInfo:
    """Tests for request_missing_info method"""

    @pytest.fixture
    def manager(self):
        return InteractionManager()

    @pytest.mark.asyncio
    async def test_request_with_high_priority(self, manager):
        """Test requesting high priority missing info"""
        missing_info = {
            "high_priority": [
                {
                    "name": "material",
                    "description": "Screw material",
                    "example": "Stainless steel",
                    "impact": "Affects torque calculation",
                    "input_type": "text"
                }
            ],
            "medium_priority": [],
            "can_skip": False
        }

        result = await manager.request_missing_info(missing_info, {})

        assert isinstance(result, InfoRequestMessage)
        assert len(result.missing_items) == 1
        assert result.missing_items[0].priority == "high"

    @pytest.mark.asyncio
    async def test_request_with_medium_priority(self, manager):
        """Test requesting medium priority missing info"""
        missing_info = {
            "high_priority": [],
            "medium_priority": [
                {
                    "name": "lubrication",
                    "description": "Lubrication condition",
                    "impact": "Affects result",
                    "input_type": "text"
                }
            ],
            "can_skip": True
        }

        result = await manager.request_missing_info(missing_info, {})

        assert len(result.missing_items) == 1
        assert result.missing_items[0].priority == "medium"

    @pytest.mark.asyncio
    async def test_request_with_mixed_priorities(self, manager):
        """Test requesting mixed priority missing info"""
        missing_info = {
            "high_priority": [
                {"name": "material", "description": "Material", "impact": "Required", "input_type": "text"}
            ],
            "medium_priority": [
                {"name": "lubrication", "description": "Lubrication", "impact": "Optional", "input_type": "text"}
            ],
            "can_skip": False
        }

        result = await manager.request_missing_info(missing_info, {})

        assert len(result.missing_items) == 2

    @pytest.mark.asyncio
    async def test_request_can_skip_option(self, manager):
        """Test can_skip option in suggestions"""
        missing_info = {
            "high_priority": [],
            "medium_priority": [
                {"name": "optional", "description": "Optional", "impact": "Optional", "input_type": "text"}
            ],
            "can_skip": True
        }

        result = await manager.request_missing_info(missing_info, {})

        # Check that skip suggestion is included
        # The last suggestion should mention skip or default
        assert len(result.suggestions) > 0

    @pytest.mark.asyncio
    async def test_request_sets_pending_interaction(self, manager):
        """Test that pending interaction is set"""
        missing_info = {
            "high_priority": [
                {"name": "material", "description": "Material", "impact": "Required", "input_type": "text"}
            ],
            "medium_priority": [],
            "can_skip": False
        }

        await manager.request_missing_info(missing_info, {})

        assert manager._pending_interaction is not None
        assert manager._pending_interaction["type"] == InteractionType.INFO_REQUEST


class TestGeneratePreview:
    """Tests for generate_preview method"""

    @pytest.fixture
    def manager(self):
        return InteractionManager()

    @pytest.mark.asyncio
    async def test_generate_preview_create(self, manager):
        """Test generating preview for create intent"""
        intent = {"type": "create"}
        collected_info = {"document_type": "Process card"}
        context = {}

        result = await manager.generate_preview(intent, collected_info, context)

        assert isinstance(result, PreviewMessage)
        # Direction should contain some text
        assert len(result.direction) > 0

    @pytest.mark.asyncio
    async def test_generate_preview_edit(self, manager):
        """Test generating preview for edit intent"""
        intent = {"type": "edit"}
        collected_info = {"target_section": "Process 3"}
        context = {}

        result = await manager.generate_preview(intent, collected_info, context)

        assert isinstance(result, PreviewMessage)

    @pytest.mark.asyncio
    async def test_generate_preview_calculate(self, manager):
        """Test generating preview for calculate intent"""
        intent = {"type": "calculate"}
        collected_info = {}
        context = {}

        result = await manager.generate_preview(intent, collected_info, context)

        assert isinstance(result, PreviewMessage)

    @pytest.mark.asyncio
    async def test_generate_preview_proofread(self, manager):
        """Test generating preview for proofread intent"""
        intent = {"type": "proofread"}
        collected_info = {"check_type": "terminology"}
        context = {}

        result = await manager.generate_preview(intent, collected_info, context)

        assert isinstance(result, PreviewMessage)

    @pytest.mark.asyncio
    async def test_generate_preview_review(self, manager):
        """Test generating preview for review intent"""
        intent = {"type": "review"}
        collected_info = {}
        context = {}

        result = await manager.generate_preview(intent, collected_info, context)

        assert isinstance(result, PreviewMessage)

    @pytest.mark.asyncio
    async def test_generate_preview_sets_pending(self, manager):
        """Test that pending interaction is set"""
        intent = {"type": "create"}
        collected_info = {}
        context = {}

        await manager.generate_preview(intent, collected_info, context)

        assert manager._pending_interaction is not None
        assert manager._pending_interaction["type"] == InteractionType.PREVIEW


class TestGenerateConfirmation:
    """Tests for generate_confirmation method"""

    @pytest.fixture
    def manager(self):
        return InteractionManager()

    @pytest.mark.asyncio
    async def test_generate_confirmation_default_options(self, manager):
        """Test generating confirmation with default options"""
        result = await manager.generate_confirmation("Confirm execution?", [])

        assert isinstance(result, ConfirmationMessage)
        assert len(result.options) == 3
        option_values = [opt.value for opt in result.options]
        assert "confirm" in option_values
        assert "modify" in option_values
        assert "cancel" in option_values

    @pytest.mark.asyncio
    async def test_generate_confirmation_custom_options(self, manager):
        """Test generating confirmation with custom options"""
        custom_options = [
            {"label": "Yes", "value": "yes"},
            {"label": "No", "value": "no"}
        ]

        result = await manager.generate_confirmation("Confirm?", custom_options)

        assert len(result.options) == 2
        assert result.options[0].label == "Yes"

    @pytest.mark.asyncio
    async def test_generate_confirmation_sets_pending(self, manager):
        """Test that pending interaction is set"""
        await manager.generate_confirmation("Confirm?", [])

        assert manager._pending_interaction is not None
        assert manager._pending_interaction["type"] == InteractionType.CONFIRMATION


class TestProcessUserResponse:
    """Tests for process_user_response method"""

    @pytest.fixture
    def manager(self):
        return InteractionManager()

    @pytest.mark.asyncio
    async def test_process_response_no_pending(self, manager):
        """Test processing response when no pending interaction"""
        response = UserResponse(
            session_id="session_123",
            content="test"
        )

        result = await manager.process_user_response(response)

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_process_text_response_to_info_request(self, manager):
        """Test processing text response to info request"""
        # Set up pending interaction
        manager._pending_interaction = {
            "type": InteractionType.INFO_REQUEST,
            "missing_items": []
        }

        response = UserResponse(
            session_id="session_123",
            response_type=InputType.TEXT,
            content="material=stainless steel"
        )

        result = await manager.process_user_response(response)

        assert result["success"] is True
        assert result["action"] == "continue_assessment"
        assert "collected_info" in result
        assert manager._pending_interaction is None  # Cleared after processing

    @pytest.mark.asyncio
    async def test_process_file_response(self, manager):
        """Test processing file response"""
        manager._pending_interaction = {
            "type": InteractionType.INFO_REQUEST,
            "missing_items": []
        }

        response = UserResponse(
            session_id="session_123",
            response_type=InputType.FILE,
            content=["/path/to/file.pdf"]
        )

        result = await manager.process_user_response(response)

        assert result["success"] is True
        assert "uploaded_files" in result["collected_info"]

    @pytest.mark.asyncio
    async def test_process_confirmation_confirm(self, manager):
        """Test processing confirmation with confirm"""
        manager._pending_interaction = {
            "type": InteractionType.CONFIRMATION,
            "options": []
        }

        response = UserResponse(
            session_id="session_123",
            content="",
            selected_option="confirm"
        )

        result = await manager.process_user_response(response)

        assert result["success"] is True
        # The action depends on the pending type
        assert "action" in result

    @pytest.mark.asyncio
    async def test_process_confirmation_cancel(self, manager):
        """Test processing confirmation with cancel"""
        manager._pending_interaction = {
            "type": InteractionType.CONFIRMATION,
            "options": []
        }

        response = UserResponse(
            session_id="session_123",
            content="",
            selected_option="cancel"
        )

        result = await manager.process_user_response(response)

        # Cancel action should be returned
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_process_preview_confirm(self, manager):
        """Test processing preview confirmation"""
        manager._pending_interaction = {
            "type": InteractionType.PREVIEW,
            "intent": {},
            "collected_info": {}
        }

        response = UserResponse(
            session_id="session_123",
            content="",
            selected_option="confirm"
        )

        result = await manager.process_user_response(response)

        assert "action" in result

    @pytest.mark.asyncio
    async def test_process_preview_modify(self, manager):
        """Test processing preview modification request"""
        manager._pending_interaction = {
            "type": InteractionType.PREVIEW,
            "intent": {},
            "collected_info": {}
        }

        response = UserResponse(
            session_id="session_123",
            content="",
            selected_option="modify"
        )

        result = await manager.process_user_response(response)

        assert "action" in result


class TestExtractInfoFromResponse:
    """Tests for _extract_info_from_response method"""

    @pytest.fixture
    def manager(self):
        return InteractionManager()

    def test_extract_key_value_with_equals(self, manager):
        """Test extracting key=value pairs"""
        response = UserResponse(
            session_id="session_123",
            response_type=InputType.TEXT,
            content="material=stainless steel,grade=8.8"
        )

        result = manager._extract_info_from_response(response)

        assert result["material"] == "stainless steel"
        assert result["grade"] == "8.8"

    def test_extract_key_value_with_colon(self, manager):
        """Test extracting key: value pairs"""
        response = UserResponse(
            session_id="session_123",
            response_type=InputType.TEXT,
            content="material: stainless steel"
        )

        result = manager._extract_info_from_response(response)

        assert result["material"] == "stainless steel"

    def test_extract_plain_text(self, manager):
        """Test extracting plain text as user_input"""
        response = UserResponse(
            session_id="session_123",
            response_type=InputType.TEXT,
            content="This is plain text"
        )

        result = manager._extract_info_from_response(response)

        assert result["user_input"] == "This is plain text"

    def test_extract_single_file(self, manager):
        """Test extracting single file"""
        response = UserResponse(
            session_id="session_123",
            response_type=InputType.FILE,
            content="/path/to/file.pdf"
        )

        result = manager._extract_info_from_response(response)

        assert "uploaded_files" in result
        assert len(result["uploaded_files"]) == 1

    def test_extract_multiple_files(self, manager):
        """Test extracting multiple files"""
        response = UserResponse(
            session_id="session_123",
            response_type=InputType.FILE,
            content=["/path/file1.pdf", "/path/file2.pdf"]
        )

        result = manager._extract_info_from_response(response)

        assert len(result["uploaded_files"]) == 2

    def test_extract_images(self, manager):
        """Test extracting images"""
        response = UserResponse(
            session_id="session_123",
            response_type=InputType.IMAGE,
            content=["/path/image1.png"]
        )

        result = manager._extract_info_from_response(response)

        assert "uploaded_images" in result

    def test_extract_with_additional_info(self, manager):
        """Test extracting with additional info"""
        response = UserResponse(
            session_id="session_123",
            response_type=InputType.TEXT,
            content="Stainless steel",
            additional_info={"source": "manual", "confidence": 0.9}
        )

        result = manager._extract_info_from_response(response)

        assert result["source"] == "manual"
        assert result["confidence"] == 0.9


class TestPendingInteractionManagement:
    """Tests for pending interaction management"""

    @pytest.fixture
    def manager(self):
        return InteractionManager()

    def test_is_awaiting_input_false_initially(self, manager):
        """Test that initially not awaiting input"""
        assert manager.is_awaiting_input() is False

    def test_is_awaiting_input_true_after_request(self, manager):
        """Test awaiting input after info request"""
        manager._pending_interaction = {"type": InteractionType.INFO_REQUEST}

        assert manager.is_awaiting_input() is True

    def test_get_pending_interaction(self, manager):
        """Test getting pending interaction"""
        manager._pending_interaction = {"type": InteractionType.CONFIRMATION}

        result = manager.get_pending_interaction()

        assert result["type"] == InteractionType.CONFIRMATION

    def test_clear_pending_interaction(self, manager):
        """Test clearing pending interaction"""
        manager._pending_interaction = {"type": InteractionType.INFO_REQUEST}

        manager.clear_pending_interaction()

        assert manager._pending_interaction is None


class TestDirectionGeneration:
    """Tests for _generate_direction method"""

    @pytest.fixture
    def manager(self):
        return InteractionManager()

    def test_generate_direction_create(self, manager):
        """Test direction generation for create"""
        result = manager._generate_direction("create", {"document_type": "process card"})
        assert result is not None
        assert len(result) > 0

    def test_generate_direction_edit(self, manager):
        """Test direction generation for edit"""
        result = manager._generate_direction("edit", {"target_section": "process 3"})
        assert result is not None

    def test_generate_direction_unknown(self, manager):
        """Test direction generation for unknown type"""
        result = manager._generate_direction("unknown", {})
        assert result is not None


class TestExpectedResultGeneration:
    """Tests for _generate_expected_result method"""

    @pytest.fixture
    def manager(self):
        return InteractionManager()

    def test_expected_result_create(self, manager):
        """Test expected result for create"""
        result = manager._generate_expected_result("create", {})
        assert result is not None

    def test_expected_result_edit(self, manager):
        """Test expected result for edit"""
        result = manager._generate_expected_result("edit", {})
        assert result is not None

    def test_expected_result_calculate(self, manager):
        """Test expected result for calculate"""
        result = manager._generate_expected_result("calculate", {})
        assert result is not None

    def test_expected_result_proofread(self, manager):
        """Test expected result for proofread"""
        result = manager._generate_expected_result("proofread", {})
        assert result is not None

    def test_expected_result_review(self, manager):
        """Test expected result for review"""
        result = manager._generate_expected_result("review", {})
        assert result is not None
