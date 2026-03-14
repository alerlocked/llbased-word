# -*- coding: utf-8 -*-
"""
Unit tests for interaction_models module

Tests the Pydantic models for user interaction.
"""
import pytest
from pydantic import ValidationError

from app.agents.orchestrator.interaction_models import (
    InteractionType,
    InputType,
    MissingInfoItem,
    ConfirmOption,
    BaseInteractionMessage,
    InfoRequestMessage,
    PreviewMessage,
    ConfirmationMessage,
    ProgressMessage,
    ResultMessage,
    ErrorMessage,
    UserResponse,
)


class TestInteractionType:
    """Tests for InteractionType enum"""

    def test_all_types_defined(self):
        """Test all interaction types are defined"""
        assert InteractionType.INFO_REQUEST.value == "info_request"
        assert InteractionType.PREVIEW.value == "preview"
        assert InteractionType.CONFIRMATION.value == "confirmation"
        assert InteractionType.PROGRESS.value == "progress"
        assert InteractionType.RESULT.value == "result"
        assert InteractionType.ERROR.value == "error"


class TestInputType:
    """Tests for InputType enum"""

    def test_all_types_defined(self):
        """Test all input types are defined"""
        assert InputType.TEXT.value == "text"
        assert InputType.IMAGE.value == "image"
        assert InputType.FILE.value == "file"
        assert InputType.FOLDER.value == "folder"


class TestMissingInfoItem:
    """Tests for MissingInfoItem model"""

    def test_create_minimal(self):
        """Test creating with minimal fields"""
        item = MissingInfoItem(
            name="screw_spec",
            description="Screw specification",
            impact="Affects calculation"
        )

        assert item.name == "screw_spec"
        assert item.description == "Screw specification"
        assert item.example is None
        assert item.priority == "medium"
        assert item.input_type == "text"

    def test_create_full(self):
        """Test creating with all fields"""
        item = MissingInfoItem(
            name="material",
            description="Screw material",
            example="Stainless steel",
            impact="Affects torque calculation",
            priority="high",
            input_type="text"
        )

        assert item.name == "material"
        assert item.example == "Stainless steel"
        assert item.impact == "Affects torque calculation"
        assert item.priority == "high"

    def test_required_fields(self):
        """Test that required fields are enforced"""
        with pytest.raises(ValidationError):
            MissingInfoItem()

        with pytest.raises(ValidationError):
            MissingInfoItem(name="test")

        # Need at least name, description, and impact
        with pytest.raises(ValidationError):
            MissingInfoItem(name="test", description="Test")


class TestConfirmOption:
    """Tests for ConfirmOption model"""

    def test_create_minimal(self):
        """Test creating with minimal fields"""
        option = ConfirmOption(label="Confirm", value="confirm")

        assert option.label == "Confirm"
        assert option.value == "confirm"
        assert option.description is None

    def test_create_full(self):
        """Test creating with all fields"""
        option = ConfirmOption(
            label="Confirm Execute",
            value="confirm",
            description="Start processing task"
        )

        assert option.label == "Confirm Execute"
        assert option.description == "Start processing task"


class TestInfoRequestMessage:
    """Tests for InfoRequestMessage model"""

    def test_create_minimal(self):
        """Test creating with minimal fields"""
        msg = InfoRequestMessage(
            message="More information needed",
            missing_items=[]
        )

        assert msg.message == "More information needed"
        assert msg.interaction_type == InteractionType.INFO_REQUEST
        assert msg.requires_response is True
        assert msg.can_skip is False

    def test_create_full(self):
        """Test creating with all fields"""
        msg = InfoRequestMessage(
            session_id="session_123",
            message="Missing information detected",
            missing_items=[
                MissingInfoItem(
                    name="material",
                    description="Material type",
                    impact="Affects result"
                )
            ],
            suggestions=["Stainless steel", "Carbon steel"],
            can_skip=True
        )

        assert msg.session_id == "session_123"
        assert len(msg.missing_items) == 1
        assert len(msg.suggestions) == 2
        assert msg.can_skip is True

    def test_timestamp_auto_generated(self):
        """Test that timestamp is auto-generated"""
        msg = InfoRequestMessage(
            message="test",
            missing_items=[]
        )

        assert msg.timestamp is not None


class TestPreviewMessage:
    """Tests for PreviewMessage model"""

    def test_create_preview(self):
        """Test creating a preview message"""
        msg = PreviewMessage(
            direction="Will calculate torque for M8 stainless steel screw",
            expected_result="Output recommended torque range (Nm)"
        )

        assert msg.interaction_type == InteractionType.PREVIEW
        assert msg.direction == "Will calculate torque for M8 stainless steel screw"
        assert msg.expected_result == "Output recommended torque range (Nm)"


class TestConfirmationMessage:
    """Tests for ConfirmationMessage model"""

    def test_create_with_options(self):
        """Test creating with options"""
        msg = ConfirmationMessage(
            message="Confirm execution?",
            options=[
                ConfirmOption(label="Confirm", value="confirm"),
                ConfirmOption(label="Cancel", value="cancel")
            ]
        )

        assert msg.interaction_type == InteractionType.CONFIRMATION
        assert len(msg.options) == 2

    def test_create_with_preview(self):
        """Test creating with associated preview"""
        preview = PreviewMessage(
            direction="Processing direction",
            expected_result="Expected result"
        )

        msg = ConfirmationMessage(
            message="Confirm?",
            options=[ConfirmOption(label="OK", value="ok")],
            preview=preview
        )

        assert msg.preview is not None
        assert msg.preview.direction == "Processing direction"


class TestProgressMessage:
    """Tests for ProgressMessage model"""

    def test_create_progress(self):
        """Test creating a progress message"""
        msg = ProgressMessage(
            current_step="2",
            total_steps=4,
            step_description="Searching knowledge base...",
            percentage=50
        )

        assert msg.interaction_type == InteractionType.PROGRESS
        assert msg.percentage == 50
        assert msg.total_steps == 4

    def test_progress_no_response_needed(self):
        """Test that progress typically doesn't need response"""
        msg = ProgressMessage(
            current_step="1",
            total_steps=3,
            step_description="Processing",
            percentage=33
        )

        # Progress messages typically don't require response
        # but the default is True, can be overridden
        assert msg.requires_response is True  # Default


class TestResultMessage:
    """Tests for ResultMessage model"""

    def test_create_success_result(self):
        """Test creating a success result"""
        msg = ResultMessage(
            success=True,
            message="Processing complete",
            data={"result": "value"},
            suggestions=["Download result", "Continue editing"]
        )

        assert msg.interaction_type == InteractionType.RESULT
        assert msg.success is True
        assert msg.data == {"result": "value"}

    def test_create_failure_result(self):
        """Test creating a failure result"""
        msg = ResultMessage(
            success=False,
            message="Processing failed"
        )

        assert msg.success is False
        assert msg.data is None


class TestErrorMessage:
    """Tests for ErrorMessage model"""

    def test_create_error(self):
        """Test creating an error message"""
        msg = ErrorMessage(
            error_code="PROCESSING_FAILED",
            error_message="Error occurred during processing",
            suggestions=["Please retry", "Contact support"],
            can_retry=True
        )

        assert msg.interaction_type == InteractionType.ERROR
        assert msg.error_code == "PROCESSING_FAILED"
        assert msg.can_retry is True

    def test_error_default_can_retry(self):
        """Test that can_retry defaults to True"""
        msg = ErrorMessage(
            error_code="ERROR",
            error_message="Error occurred"
        )

        assert msg.can_retry is True


class TestUserResponse:
    """Tests for UserResponse model"""

    def test_create_text_response(self):
        """Test creating a text response"""
        response = UserResponse(
            session_id="session_123",
            response_type=InputType.TEXT,
            content="Stainless steel A2-70"
        )

        assert response.session_id == "session_123"
        assert response.response_type == InputType.TEXT
        assert response.content == "Stainless steel A2-70"
        assert response.selected_option is None

    def test_create_option_response(self):
        """Test creating an option selection response"""
        response = UserResponse(
            session_id="session_123",
            content="",  # Need to provide content
            selected_option="confirm"
        )

        assert response.selected_option == "confirm"

    def test_create_file_response(self):
        """Test creating a file upload response"""
        response = UserResponse(
            session_id="session_123",
            response_type=InputType.FILE,
            content=["/path/to/file1.pdf", "/path/to/file2.pdf"]
        )

        assert response.response_type == InputType.FILE
        assert len(response.content) == 2

    def test_create_structured_response(self):
        """Test creating a structured data response"""
        response = UserResponse(
            session_id="session_123",
            content={
                "material": "Stainless steel",
                "strength_grade": "A2-70"
            }
        )

        assert isinstance(response.content, dict)
        assert response.content["material"] == "Stainless steel"

    def test_response_with_additional_info(self):
        """Test response with additional info"""
        response = UserResponse(
            session_id="session_123",
            content="M8",
            additional_info={
                "source": "user_input",
                "confidence": 0.95
            }
        )

        assert response.additional_info is not None
        assert response.additional_info["confidence"] == 0.95


class TestModelSerialization:
    """Tests for model serialization/deserialization"""

    def test_info_request_serialization(self):
        """Test InfoRequestMessage serialization"""
        msg = InfoRequestMessage(
            message="Need information",
            missing_items=[
                MissingInfoItem(
                    name="material",
                    description="Material type",
                    impact="Affects result"
                )
            ]
        )

        data = msg.model_dump()

        assert "message" in data
        assert "missing_items" in data
        assert len(data["missing_items"]) == 1

    def test_user_response_from_dict(self):
        """Test creating UserResponse from dict"""
        data = {
            "session_id": "session_123",
            "content": "Stainless steel",
            "selected_option": None
        }

        response = UserResponse(**data)

        assert response.session_id == "session_123"
        assert response.content == "Stainless steel"

    def test_confirmation_json_schema(self):
        """Test ConfirmationMessage JSON schema"""
        msg = ConfirmationMessage(
            message="Confirm?",
            options=[ConfirmOption(label="OK", value="ok")]
        )

        schema = msg.model_json_schema()

        assert "properties" in schema
        assert "message" in schema["properties"]
        assert "options" in schema["properties"]
