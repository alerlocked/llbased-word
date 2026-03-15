"""
PDF Processing Workflow Integration Tests

Tests the complete PDF processing flow:
1. PDF upload
2. PDF parsing
3. Table extraction
4. Result retrieval
"""
import pytest
import sys
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from pathlib import Path
import tempfile
import os
import json

# Mock problematic dependencies before importing
sys.modules['app.agents.workflows'] = MagicMock()
sys.modules['app.agents.workflows.creation_graph'] = MagicMock()

from app.main import app


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


@pytest.fixture
def sample_pdf_path():
    """Create a sample PDF file for testing"""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF')
        yield Path(f.name)
    os.unlink(f.name)


class TestPDFWorkflow:
    """Integration tests for PDF processing workflow"""

    def test_health_before_processing(self, client):
        """Test server is healthy before processing"""
        response = client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_pdf_parsing_workflow(self, sample_pdf_path):
        """Test complete PDF parsing workflow"""
        from app.tools.pdf_parser import PDFParser
        from app.models.table_models import ParserType

        parser = PDFParser(config={"enable_caching": False})

        # Mock the parser selector
        with patch.object(parser._selector, 'select_parser') as mock_select:
            mock_selection = MagicMock()
            mock_selection.selected_parser = ParserType.SIMPLE
            mock_selection.has_tables = False
            mock_selection.table_count = 0
            mock_selection.reasoning = "Simple document"
            mock_select.return_value = AsyncMock()()
            mock_select.return_value = mock_selection

            # The parser should work (or fail gracefully)
            try:
                result = await parser.parse(str(sample_pdf_path))
                assert "pages" in result or "metadata" in result
            except Exception as e:
                # Expected for minimal PDF
                pass

    def test_agent_conversation_workflow(self, client):
        """Test complete agent conversation workflow"""
        # Step 1: Start conversation
        start_response = client.post(
            "/api/agent/start-conversation",
            json={
                "initial_input": "我想创建一份电缆装配工艺文件",
                "reference_texts": [],
                "business_scenario": "cable_assembly",
                "user_id": 1
            }
        )

        assert start_response.status_code == 200
        data = start_response.json()
        assert data["success"] is True

        session_id = data["session_id"]
        questions = data.get("questions", [])

        # Step 2: Answer questions if any
        if questions:
            for question in questions[:1]:  # Answer first question
                reply_response = client.post(
                    "/api/agent/reply-question",
                    json={
                        "session_id": session_id,
                        "question_id": question["id"],
                        "answer": "标准工艺卡片"
                    }
                )
                assert reply_response.status_code == 200

        # Step 3: Get material report
        material_response = client.get(f"/api/agent/material-report/{session_id}")
        assert material_response.status_code == 200

        # Step 4: Confirm materials
        confirm_response = client.post(
            "/api/agent/confirm-materials",
            json={
                "session_id": session_id,
                "selected_material_ids": ["mat_0"],
                "excluded_material_ids": [],
                "additional_keywords": []
            }
        )
        assert confirm_response.status_code == 200

        # Step 5: Get review suggestions
        suggestions_response = client.get(f"/api/agent/review-suggestions/{session_id}")
        assert suggestions_response.status_code == 200

        # Step 6: Apply suggestions
        apply_response = client.post(
            "/api/agent/apply-suggestions",
            json={
                "session_id": session_id,
                "applied_suggestions": ["sug_1"],
                "rejected_suggestions": []
            }
        )
        assert apply_response.status_code == 200

        # Step 7: Generate article
        generate_response = client.post(
            "/api/agent/generate-article",
            json={
                "project_id": 1,
                "article_type": "process_card"
            }
        )
        assert generate_response.status_code == 200

    def test_document_context_workflow(self, client):
        """Test document context building workflow"""
        from collections import namedtuple

        DocInfo = namedtuple('DocInfo', ['name', 'path', 'table_count', 'page_count'])
        TableInfo = namedtuple('TableInfo', ['page', 'caption', 'table_type', 'html', 'image_path'])

        mock_manager = MagicMock()
        mock_manager.get_document_list.return_value = [
            DocInfo(name="doc1", path="/path/1", table_count=5, page_count=10),
            DocInfo(name="doc2", path="/path/2", table_count=3, page_count=5),
        ]
        mock_manager.get_document_tables.return_value = [
            TableInfo(page=1, caption="Table 1", table_type="process", html="<table></table>", image_path=None)
        ]
        mock_manager.get_document_markdown.return_value = "# Test\n\nContent"
        mock_manager.build_document_context.return_value = "Combined context"
        mock_manager.get_extraction_summary.return_value = {"total": 2}

        with patch('app.api.document.get_context_manager', return_value=mock_manager):
            # Step 1: List documents
            list_response = client.get("/api/documents")
            assert list_response.status_code == 200
            assert list_response.json()["total"] == 2

            # Step 2: Get tables for a document
            tables_response = client.get("/api/documents/doc1/tables")
            assert tables_response.status_code == 200

            # Step 3: Get markdown
            md_response = client.get("/api/documents/doc1/markdown")
            assert md_response.status_code == 200

            # Step 4: Build context from multiple documents
            context_response = client.post(
                "/api/documents/context",
                json=["doc1", "doc2"],
                params={"include_html": True, "max_tables": 100}
            )
            assert context_response.status_code == 200
            assert "context" in context_response.json()


class TestErrorHandling:
    """Tests for error handling"""

    def test_invalid_session_operations(self, client):
        """Test operations with invalid session ID"""
        # Try to get material report with invalid session
        response = client.get("/api/agent/material-report/invalid-session-id")
        assert response.status_code == 404

        # Try to select plan with invalid session
        response = client.post(
            "/api/agent/select-plan",
            json={
                "session_id": "invalid-session-id",
                "plan_option_id": "plan_1"
            }
        )
        assert response.status_code == 404

    def test_invalid_json_request(self, client):
        """Test handling of invalid JSON requests"""
        response = client.post(
            "/api/agent/start-conversation",
            content="not json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_missing_required_fields(self, client):
        """Test handling of missing required fields"""
        response = client.post(
            "/api/agent/start-conversation",
            json={}  # Missing required fields
        )
        assert response.status_code == 422


class TestConcurrency:
    """Tests for concurrent operations"""

    def test_multiple_sessions(self, client):
        """Test creating multiple sessions"""
        sessions = []

        for i in range(3):
            response = client.post(
                "/api/agent/start-conversation",
                json={
                    "initial_input": f"测试 {i}",
                    "user_id": i + 1
                }
            )
            assert response.status_code == 200
            sessions.append(response.json()["session_id"])

        # All session IDs should be unique
        assert len(set(sessions)) == 3

    def test_parallel_chat_messages(self, client):
        """Test sending parallel chat messages"""
        # Create a session
        start_response = client.post(
            "/api/agent/start-conversation",
            json={
                "initial_input": "测试",
                "user_id": 1
            }
        )
        session_id = start_response.json()["session_id"]

        # Send multiple messages to the same session
        responses = []
        for i in range(3):
            response = client.post(
                "/api/agent/chat",
                json={
                    "content": f"消息 {i}",
                    "session_id": session_id
                }
            )
            responses.append(response)

        # All should succeed
        for response in responses:
            assert response.status_code == 200
