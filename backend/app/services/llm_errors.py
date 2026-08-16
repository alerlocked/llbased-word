"""LLM error classification and per-class mitigation policies.

Separate from llm_service.py so callers (e.g. writing_agent) can classify
errors without importing client config; llm_service stays transport-only.
"""
import re
from enum import Enum
from typing import Dict, List


class LLMErrorClass(str, Enum):
    TIMEOUT = "timeout"
    CONNECTION_REFUSED = "connection_refused"
    CONTEXT_OVERFLOW = "context_overflow"
    EMPTY_REPLY = "empty_reply"
    JSON_PARSE_FAIL = "json_parse_fail"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"


# Readable Chinese messages surfaced to end users (via SSE error events).
USER_FACING_MESSAGES: Dict[LLMErrorClass, str] = {
    LLMErrorClass.TIMEOUT: "模型响应超时，正在自动重试",
    LLMErrorClass.CONNECTION_REFUSED: "无法连接本地模型服务，请检查模型是否已启动",
    LLMErrorClass.CONTEXT_OVERFLOW: "输入内容超出模型上下文长度，已尝试压缩后重试",
    LLMErrorClass.EMPTY_REPLY: "模型返回了空内容，正在自动重试",
    LLMErrorClass.JSON_PARSE_FAIL: "模型输出格式异常，正在自动重试",
    LLMErrorClass.RATE_LIMIT: "模型服务请求过多，正在等待重试",
    LLMErrorClass.UNKNOWN: "模型服务异常",
}

# Error classes worth retrying (idempotent calls, transient failure modes).
_RETRYABLE = {
    LLMErrorClass.TIMEOUT,
    LLMErrorClass.CONNECTION_REFUSED,
    LLMErrorClass.RATE_LIMIT,
    LLMErrorClass.EMPTY_REPLY,
    LLMErrorClass.JSON_PARSE_FAIL,
    LLMErrorClass.UNKNOWN,
}

_OVERFLOW_PATTERNS = re.compile(
    r"context length|maximum context|context window|too many tokens|"
    r"input tokens.*exceed|exceeds.*context|上下文长度|超出上下文",
    re.IGNORECASE,
)
_TIMEOUT_PATTERNS = re.compile(
    r"timeout|timed out|read timeout|请求超时|响应超时",
    re.IGNORECASE,
)
_CONN_PATTERNS = re.compile(
    r"connection refused|connect error|connect call failed|"
    r"connection reset|peer closed|拒绝连接|无法连接|连接失败",
    re.IGNORECASE,
)
_RATE_PATTERNS = re.compile(r"429|rate limit|too many requests|访问过于频繁|限流", re.IGNORECASE)
_EMPTY_PATTERNS = re.compile(r"empty (reply|content|response)|空回复|空内容", re.IGNORECASE)


def classify_error_text(text: str) -> LLMErrorClass:
    """Classify an error from its string representation (regex-based)."""
    if not text:
        return LLMErrorClass.UNKNOWN
    if _OVERFLOW_PATTERNS.search(text):
        return LLMErrorClass.CONTEXT_OVERFLOW
    if _RATE_PATTERNS.search(text):
        return LLMErrorClass.RATE_LIMIT
    if _CONN_PATTERNS.search(text):
        return LLMErrorClass.CONNECTION_REFUSED
    if _TIMEOUT_PATTERNS.search(text):
        return LLMErrorClass.TIMEOUT
    if _EMPTY_PATTERNS.search(text):
        return LLMErrorClass.EMPTY_REPLY
    return LLMErrorClass.UNKNOWN


def classify_exception(exc: BaseException) -> LLMErrorClass:
    """Classify an exception raised by the LLM client stack."""
    # Import lazily: httpx/openai are transport deps of llm_service, but this
    # module must stay importable without them (unit tests, writing_agent).
    try:
        import httpx
        if isinstance(exc, httpx.TimeoutException):
            return LLMErrorClass.TIMEOUT
        if isinstance(exc, httpx.ConnectError):
            return LLMErrorClass.CONNECTION_REFUSED
    except ImportError:
        pass
    try:
        import openai
        if isinstance(exc, openai.APITimeoutError):
            return LLMErrorClass.TIMEOUT
        if isinstance(exc, openai.APIConnectionError):
            return LLMErrorClass.CONNECTION_REFUSED
        if isinstance(exc, openai.RateLimitError):
            return LLMErrorClass.RATE_LIMIT
        # Name varies across openai versions: BadRequestError (new) /
        # BadRequestException (old); both mean HTTP 400 (context overflow etc.)
        bad_request = getattr(openai, "BadRequestError", None) or getattr(
            openai, "BadRequestException", None
        )
        if bad_request and isinstance(exc, bad_request):
            return classify_error_text(str(exc))
    except ImportError:
        pass
    status = getattr(exc, "status_code", None)
    if status == 429:
        return LLMErrorClass.RATE_LIMIT
    return classify_error_text(str(exc))


def should_retry(error_class: LLMErrorClass, attempt: int, max_retries: int = 2) -> bool:
    """Whether another retry is worthwhile for this class after `attempt` tries.

    CONTEXT_OVERFLOW is excluded: the caller applies one context trim then
    retries once via its own logic; blind retries without trimming cannot help.
    """
    return error_class in _RETRYABLE and attempt < max_retries


def trim_messages_for_overflow(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Mitigation for context overflow: halve the largest user message content.

    System messages (where JSON/format instructions live) are never touched.
    Returns a new list; the input is not mutated.
    """
    if not messages:
        return messages
    trimmed = [dict(m) for m in messages]
    user_indices = [i for i, m in enumerate(trimmed) if m.get("role") == "user"]
    if not user_indices:
        return trimmed
    largest = max(user_indices, key=lambda i: len(trimmed[i].get("content", "") or ""))
    content = trimmed[largest].get("content", "") or ""
    half = len(content) // 2
    trimmed[largest]["content"] = content[:half]
    return trimmed
