"""Unit tests for LLM error classification module."""
import pytest

from app.services.llm_errors import (
    LLMErrorClass,
    classify_error_text,
    classify_exception,
    should_retry,
    trim_messages_for_overflow,
    USER_FACING_MESSAGES,
)


class TestClassifyErrorText:
    def test_timeout_patterns(self):
        assert classify_error_text("Request timed out") == LLMErrorClass.TIMEOUT
        assert classify_error_text("Read timeout after 300s") == LLMErrorClass.TIMEOUT

    def test_connection_patterns(self):
        assert classify_error_text("Connection refused to 127.0.0.1:1028") == LLMErrorClass.CONNECTION_REFUSED
        assert classify_error_text("Connect call failed") == LLMErrorClass.CONNECTION_REFUSED

    def test_overflow_patterns(self):
        assert classify_error_text("This model's maximum context length is 32768 tokens") == LLMErrorClass.CONTEXT_OVERFLOW
        assert classify_error_text("input tokens exceed the limit") == LLMErrorClass.CONTEXT_OVERFLOW

    def test_rate_limit(self):
        assert classify_error_text("Error code: 429 - rate limit exceeded") == LLMErrorClass.RATE_LIMIT

    def test_empty(self):
        assert classify_error_text("") == LLMErrorClass.UNKNOWN

    def test_unknown(self):
        assert classify_error_text("something weird happened") == LLMErrorClass.UNKNOWN

    def test_overflow_beats_rate_limit_order(self):
        # Overflow is the most specific mitigation target; check it wins even
        # when the text also mentions tokens/limits.
        assert classify_error_text("context length exceeded, 429") == LLMErrorClass.CONTEXT_OVERFLOW


class TestClassifyException:
    def test_httpx_timeout(self):
        import httpx
        assert classify_exception(httpx.ReadTimeout("read timed out")) == LLMErrorClass.TIMEOUT

    def test_httpx_connect_error(self):
        import httpx
        assert classify_exception(httpx.ConnectError("connection refused")) == LLMErrorClass.CONNECTION_REFUSED

    def test_generic_exception_falls_back_to_text(self):
        assert classify_exception(RuntimeError("Request timed out")) == LLMErrorClass.TIMEOUT

    def test_plain_exception_unknown(self):
        assert classify_exception(ValueError("bad value")) == LLMErrorClass.UNKNOWN


class TestShouldRetry:
    def test_retryable_within_budget(self):
        assert should_retry(LLMErrorClass.TIMEOUT, attempt=0) is True
        assert should_retry(LLMErrorClass.TIMEOUT, attempt=1) is True

    def test_retryable_exhausted(self):
        assert should_retry(LLMErrorClass.TIMEOUT, attempt=2) is False

    def test_overflow_not_blindly_retried(self):
        assert should_retry(LLMErrorClass.CONTEXT_OVERFLOW, attempt=0) is False

    def test_all_classes_have_user_message(self):
        for cls in LLMErrorClass:
            assert cls in USER_FACING_MESSAGES
            assert USER_FACING_MESSAGES[cls]


class TestTrimMessagesForOverflow:
    def test_halves_largest_user_message(self):
        msgs = [
            {"role": "system", "content": "instructions " * 10},
            {"role": "user", "content": "x" * 100},
            {"role": "user", "content": "y" * 20},
        ]
        trimmed = trim_messages_for_overflow(msgs)
        assert len(trimmed[1]["content"]) == 50
        assert trimmed[2]["content"] == "y" * 20  # smaller user msg untouched

    def test_system_never_touched(self):
        sys_content = "do not touch " * 50
        msgs = [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": "short"},
        ]
        trimmed = trim_messages_for_overflow(msgs)
        assert trimmed[0]["content"] == sys_content

    def test_input_not_mutated(self):
        msgs = [{"role": "user", "content": "x" * 100}]
        trim_messages_for_overflow(msgs)
        assert len(msgs[0]["content"]) == 100

    def test_no_user_messages_returns_copy(self):
        msgs = [{"role": "system", "content": "only system"}]
        assert trim_messages_for_overflow(msgs) == msgs

    def test_empty(self):
        assert trim_messages_for_overflow([]) == []
