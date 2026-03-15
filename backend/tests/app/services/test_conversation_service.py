"""
Tests for ConversationService

Validates:
1. Session creation
2. Session retrieval
3. Session update
4. State persistence
5. State restoration
"""
import pytest
import sys
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any

# Mock the problematic dependencies before importing
sys.modules['app.agents.workflows'] = MagicMock()
sys.modules['app.agents.workflows.creation_graph'] = MagicMock()

from app.services.conversation_service import (
    ConversationService,
    get_conversation_service,
)


class TestConversationService:
    """Tests for ConversationService"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        db = MagicMock()
        return db

    @pytest.fixture
    def service(self):
        """Create a ConversationService instance"""
        return ConversationService()

    def test_create_session(self, service, mock_db):
        """Test creating a new session"""
        # Setup mock
        mock_session = MagicMock()
        mock_session.session_id = "test-session-id"
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda x: setattr(x, 'session_id', 'test-session-id'))

        # Mock the database model
        with patch('app.services.conversation_service.ConversationSession') as MockSession:
            MockSession.return_value = mock_session
            result = service.create_session(mock_db, user_id=1, project_id=1)

            assert result is not None
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    def test_create_session_with_initial_state(self, service, mock_db):
        """Test creating a session with initial state"""
        initial_state = {"key": "value", "nested": {"data": 123}}

        with patch('app.services.conversation_service.ConversationSession') as MockSession:
            mock_session = MagicMock()
            MockSession.return_value = mock_session

            result = service.create_session(
                mock_db,
                user_id=1,
                initial_state=initial_state
            )

            # Verify state was passed
            call_args = MockSession.call_args
            assert call_args is not None

    def test_get_session(self, service, mock_db):
        """Test getting an existing session"""
        # Setup mock
        mock_session = MagicMock()
        mock_session.session_id = "test-session-id"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query

        result = service.get_session(mock_db, "test-session-id")

        assert result is not None
        mock_db.query.assert_called_once()

    def test_get_session_not_found(self, service, mock_db):
        """Test getting a non-existent session"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = service.get_session(mock_db, "nonexistent-id")

        assert result is None

    def test_update_session(self, service, mock_db):
        """Test updating a session"""
        # Setup mock
        mock_session = MagicMock()
        mock_session.session_id = "test-session-id"
        mock_session.state_data = {}

        with patch.object(service, 'get_session', return_value=mock_session):
            result = service.update_session(
                mock_db,
                "test-session-id",
                current_step="updated_step",
                state_data={"new_key": "new_value"}
            )

            assert result is not None
            assert mock_session.current_step == "updated_step"
            mock_db.commit.assert_called_once()

    def test_update_session_not_found(self, service, mock_db):
        """Test updating a non-existent session"""
        with patch.object(service, 'get_session', return_value=None):
            result = service.update_session(
                mock_db,
                "nonexistent-id",
                current_step="updated"
            )

            assert result is None

    def test_delete_session(self, service, mock_db):
        """Test deleting a session"""
        mock_session = MagicMock()

        with patch.object(service, 'get_session', return_value=mock_session):
            result = service.delete_session(mock_db, "test-session-id")

            assert result is True
            mock_db.delete.assert_called_once_with(mock_session)
            mock_db.commit.assert_called_once()

    def test_delete_session_not_found(self, service, mock_db):
        """Test deleting a non-existent session"""
        with patch.object(service, 'get_session', return_value=None):
            result = service.delete_session(mock_db, "nonexistent-id")

            assert result is False

    def test_save_state(self, service, mock_db):
        """Test saving GraphState to session"""
        mock_session = MagicMock()
        mock_session.state_data = {}

        state: Dict[str, Any] = {
            "user_input": "test input",
            "current_step": "testing",
            "conversation_history": [],
        }

        with patch.object(service, 'get_session', return_value=mock_session):
            result = service.save_state(mock_db, "test-session-id", state)

            assert result is True
            mock_db.commit.assert_called_once()

    def test_save_state_with_plan(self, service, mock_db):
        """Test saving state with TaskPlan object"""
        mock_session = MagicMock()
        mock_session.state_data = {}

        # Mock plan with model_dump method
        mock_plan = MagicMock()
        mock_plan.model_dump.return_value = {"plan_data": "test"}

        state = {
            "user_input": "test",
            "current_step": "planning",
            "plan": mock_plan,
        }

        with patch.object(service, 'get_session', return_value=mock_session):
            result = service.save_state(mock_db, "test-session-id", state)

            assert result is True

    def test_restore_state(self, service, mock_db):
        """Test restoring GraphState from session"""
        mock_session = MagicMock()
        mock_session.state_data = {
            "user_input": "restored input",
            "current_step": "restored",
            "conversation_history": [{"role": "user", "content": "test"}],
        }

        with patch.object(service, 'get_session', return_value=mock_session):
            result = service.restore_state(mock_db, "test-session-id")

            assert result is not None
            assert result["user_input"] == "restored input"
            assert result["session_id"] == "test-session-id"

    def test_restore_state_with_plan(self, service, mock_db):
        """Test restoring state with TaskPlan"""
        mock_session = MagicMock()
        mock_session.state_data = {
            "user_input": "test",
            "current_step": "planning",
            "plan": {"tasks": [], "strategy": "test"},
        }

        with patch.object(service, 'get_session', return_value=mock_session):
            with patch('app.services.conversation_service.TaskPlan') as MockTaskPlan:
                mock_plan = MagicMock()
                MockTaskPlan.return_value = mock_plan

                result = service.restore_state(mock_db, "test-session-id")

                assert result is not None

    def test_restore_state_not_found(self, service, mock_db):
        """Test restoring state from non-existent session"""
        with patch.object(service, 'get_session', return_value=None):
            result = service.restore_state(mock_db, "nonexistent-id")

            assert result is None

    def test_restore_state_empty_data(self, service, mock_db):
        """Test restoring state from session with no data"""
        mock_session = MagicMock()
        mock_session.state_data = None

        with patch.object(service, 'get_session', return_value=mock_session):
            result = service.restore_state(mock_db, "test-session-id")

            assert result is None


class TestGlobalService:
    """Tests for global service instance"""

    def test_get_conversation_service_singleton(self):
        """Test that get_conversation_service returns a singleton"""
        # Reset the global instance
        import app.services.conversation_service as module
        module._conversation_service = None

        service1 = get_conversation_service()
        service2 = get_conversation_service()

        assert service1 is service2
        assert isinstance(service1, ConversationService)
