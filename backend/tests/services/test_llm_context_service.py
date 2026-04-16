"""
Tests for LLMContextService initialization and context building.
Covers fix #1: profile_dir NameError.
"""
import pytest
from pathlib import Path
import tempfile


def test_init_does_not_raise_name_error():
    """LLMContextService.__init__ must not reference undefined variables."""
    from app.services.llm_context_service import LLMContextService

    with tempfile.TemporaryDirectory() as tmp:
        svc = LLMContextService(
            base_path=tmp,
            memory_dir=str(Path(tmp) / "memory"),
            data_dir=str(Path(tmp) / "data"),
        )
        assert svc.memory_service is not None
        assert svc.context_service is not None


def test_build_context_returns_string_and_breakdown():
    """build_context should return (context_text, token_breakdown)."""
    from app.services.llm_context_service import LLMContextService

    with tempfile.TemporaryDirectory() as tmp:
        svc = LLMContextService(
            base_path=tmp,
            memory_dir=str(Path(tmp) / "memory"),
            data_dir=str(Path(tmp) / "data"),
        )
        context, breakdown = svc.build_context(
            query="test query",
            session_id="test-session",
        )
        assert isinstance(context, str)
        assert isinstance(breakdown, dict)
        assert "system" in breakdown
        assert "memory" in breakdown
