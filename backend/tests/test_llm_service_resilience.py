"""Unit tests for llm_service resilience layer (retry/backoff/trim/classification).

Mocks _collect_stream_content with scripted side effects — no real transport.
"""
from unittest.mock import AsyncMock

import pytest

from app.services import llm_service as ls
from app.services.llm_errors import LLMErrorClass


def _collect_mock(side_effect):
    """Patch _collect_stream_content with an AsyncMock having side effects."""
    m = AsyncMock(side_effect=side_effect)
    return m


MSG = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hello"}]


class TestGenerateWithMessagesRetry:
    async def test_timeout_then_success(self, monkeypatch):
        import httpx
        collect = _collect_mock([
            httpx.ReadTimeout("read timed out"),
            ("recovered content", "stop"),
        ])
        monkeypatch.setattr(ls.llm_service, "_collect_stream_content", collect)
        result = await ls.llm_service.generate_with_messages(messages=MSG)
        assert result["status"] == "success"
        assert result["content"] == "recovered content"
        assert collect.await_count == 2

    async def test_always_fail_returns_classified_error(self, monkeypatch):
        import httpx
        collect = _collect_mock([
            httpx.ReadTimeout("read timed out"),
            httpx.ReadTimeout("read timed out"),
            httpx.ReadTimeout("read timed out"),
        ])
        monkeypatch.setattr(ls.llm_service, "_collect_stream_content", collect)
        result = await ls.llm_service.generate_with_messages(messages=MSG)
        assert result["status"] == "error"
        assert result["error_class"] == LLMErrorClass.TIMEOUT.value
        # 1 initial + 2 retries
        assert collect.await_count == 3
        # contract keys present
        for key in ("status", "content", "finish_reason", "error"):
            assert key in result

    async def test_overflow_trims_once_then_retries(self, monkeypatch):
        from openai import BadRequestError

        def make_overflow_request():
            # openai BadRequestError(httpx response) needs a response object;
            # easier: craft via __new__ to skip response wiring.
            err = BadRequestError.__new__(BadRequestError)
            Exception.__init__(err, "This model's maximum context length is 32768 tokens")
            return err

        collect = _collect_mock([
            make_overflow_request(),
            make_overflow_request(),
            ("ok after trim", "stop"),
        ])
        monkeypatch.setattr(ls.llm_service, "_collect_stream_content", collect)
        result = await ls.llm_service.generate_with_messages(
            messages=[
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "x" * 1000},
            ]
        )
        assert result["status"] == "success"
        # first call original messages, second call trimmed (halved), third same trimmed
        first_call_msgs = collect.await_args_list[0].kwargs["messages"]
        second_call_msgs = collect.await_args_list[1].kwargs["messages"]
        assert len(first_call_msgs[1]["content"]) == 1000
        assert len(second_call_msgs[1]["content"]) == 500
        third_call_msgs = collect.await_args_list[2].kwargs["messages"]
        assert len(third_call_msgs[1]["content"]) == 500  # trimmed only once
        # system message never trimmed
        assert first_call_msgs[0]["content"] == "sys"
        assert second_call_msgs[0]["content"] == "sys"

    async def test_empty_reply_then_content(self, monkeypatch):
        collect = _collect_mock([
            ("", "stop"),  # empty content
            ("real content", "stop"),
        ])
        monkeypatch.setattr(ls.llm_service, "_collect_stream_content", collect)
        result = await ls.llm_service.generate_with_messages(messages=MSG)
        assert result["status"] == "success"
        assert result["content"] == "real content"
        assert collect.await_count == 2

    async def test_empty_reply_exhausted(self, monkeypatch):
        collect = _collect_mock([("", "stop")] * 3)
        monkeypatch.setattr(ls.llm_service, "_collect_stream_content", collect)
        result = await ls.llm_service.generate_with_messages(messages=MSG)
        assert result["status"] == "error"
        assert result["error_class"] == LLMErrorClass.EMPTY_REPLY.value
        assert collect.await_count == 3


class TestGenerateTextContract:
    async def test_keeps_two_key_contract_on_success(self, monkeypatch):
        collect = _collect_mock([("content here", "stop")])
        monkeypatch.setattr(ls.llm_service, "_collect_stream_content", collect)
        result = await ls.llm_service.generate_text(prompt="test")
        assert result == {"status": "success", "content": "content here"}

    async def test_error_has_class_no_finish_reason(self, monkeypatch):
        import httpx
        collect = _collect_mock([httpx.ReadTimeout("t")] * 3)
        monkeypatch.setattr(ls.llm_service, "_collect_stream_content", collect)
        result = await ls.llm_service.generate_text(prompt="test")
        assert result["status"] == "error"
        assert "finish_reason" not in result
        assert result["error_class"] == LLMErrorClass.TIMEOUT.value
