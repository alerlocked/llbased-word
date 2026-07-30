"""Tests for IntentRecognizer — LLM classification + fail-soft keyword fallback.

Covers the 4th-step change (intent-llm-dispatch-fix): recognize() now calls an
LLM classifier with fail-soft fallback to the original keyword regex path.
"""
import pytest
from unittest.mock import AsyncMock

from app.agents.orchestrator.intent_recognizer import IntentRecognizer, IntentType


@pytest.fixture
def recognizer():
    return IntentRecognizer()


def _mock_llm(monkeypatch, content: str, status: str = "success"):
    """Make llm_service.generate_with_messages return canned content."""
    from app.services import llm_service as ls
    monkeypatch.setattr(
        ls.llm_service, "generate_with_messages",
        AsyncMock(return_value={"status": status, "content": content}),
    )


class TestLLMClassification:
    """LLM 分类各意图(mock generate_with_messages)。"""

    @pytest.mark.asyncio
    async def test_classify_create_document(self, recognizer, monkeypatch):
        _mock_llm(monkeypatch, '{"intent": "create_document"}')
        result = await recognizer.recognize("帮我创建一份装配工艺规程")
        assert result["type"] == "create_document"
        assert result["confidence"] >= 0.85

    @pytest.mark.asyncio
    async def test_classify_review_document(self, recognizer, monkeypatch):
        _mock_llm(monkeypatch, '{"intent": "review_document"}')
        result = await recognizer.recognize("审查一下这份工艺文件")
        assert result["type"] == "review_document"

    @pytest.mark.asyncio
    async def test_classify_search_knowledge(self, recognizer, monkeypatch):
        _mock_llm(monkeypatch, '{"intent": "search_knowledge"}')
        result = await recognizer.recognize("查一下密封脂的规格")
        assert result["type"] == "search_knowledge"

    @pytest.mark.asyncio
    async def test_classify_edit_document(self, recognizer, monkeypatch):
        _mock_llm(monkeypatch, '{"intent": "edit_document"}')
        result = await recognizer.recognize("修改工序5的参数")
        assert result["type"] == "edit_document"

    @pytest.mark.asyncio
    async def test_classify_with_markdown_fence(self, recognizer, monkeypatch):
        # LLM 输出带 ```json fence 也要解析
        _mock_llm(monkeypatch, '```json\n{"intent": "edit_document"}\n```')
        result = await recognizer.recognize("改一下参数")
        assert result["type"] == "edit_document"

    @pytest.mark.asyncio
    async def test_classify_with_surrounding_prose(self, recognizer, monkeypatch):
        # LLM 输出带杂文也要解析(正则兜底)
        _mock_llm(monkeypatch, '结果是 {"intent": "check_compliance"} 谢谢')
        result = await recognizer.recognize("检查合规")
        assert result["type"] == "check_compliance"


class TestFailSoftFallback:
    """LLM 失败 → 关键词正则兜底(不阻塞)。"""

    @pytest.mark.asyncio
    async def test_fallback_on_llm_error_status(self, recognizer, monkeypatch):
        _mock_llm(monkeypatch, "", status="error")
        result = await recognizer.recognize("创建新工艺文件")
        # 关键词兜底:create_document 命中"创建"
        assert result["type"] == "create_document"

    @pytest.mark.asyncio
    async def test_fallback_on_unparseable_json(self, recognizer, monkeypatch):
        _mock_llm(monkeypatch, "这不是JSON")
        result = await recognizer.recognize("搜索密封脂知识")
        # 关键词兜底:search_knowledge 命中"搜索"
        assert result["type"] == "search_knowledge"

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_intent_type(self, recognizer, monkeypatch):
        _mock_llm(monkeypatch, '{"intent": "nonexistent_type"}')
        result = await recognizer.recognize("审核工艺文件")
        # 无效类型 → 关键词兜底:review_document 命中"审核"
        assert result["type"] == "review_document"

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self, recognizer, monkeypatch):
        from app.services import llm_service as ls
        monkeypatch.setattr(
            ls.llm_service, "generate_with_messages",
            AsyncMock(side_effect=Exception("network down")),
        )
        result = await recognizer.recognize("创建工艺文件")
        assert result["type"] == "create_document"


class TestDraftCompletePriority:
    """draft_complete 复合检测优先于 LLM 结果。"""

    @pytest.mark.asyncio
    async def test_draft_complete_overrides_llm(self, recognizer, monkeypatch):
        # LLM 说 edit_document,但 draft_complete 复合检测(boost)覆盖
        _mock_llm(monkeypatch, '{"intent": "edit_document"}')
        result = await recognizer.recognize("补全工艺文件", context={"has_draft": True})
        assert result["type"] == "draft_complete"


class TestParseIntentJson:
    """_parse_intent_json 容错(照 review_service _parse_missing_params 范式)。"""

    def test_parse_plain_json(self):
        assert IntentRecognizer._parse_intent_json('{"intent": "create_document"}') == "create_document"

    def test_parse_fenced_json(self):
        raw = '```json\n{"intent": "review_document"}\n```'
        assert IntentRecognizer._parse_intent_json(raw) == "review_document"

    def test_parse_embedded_json(self):
        assert IntentRecognizer._parse_intent_json('答: {"intent": "edit_document"} 完') == "edit_document"

    def test_parse_empty(self):
        assert IntentRecognizer._parse_intent_json("") is None

    def test_parse_no_json(self):
        assert IntentRecognizer._parse_intent_json("无JSON内容") is None

    def test_parse_no_intent_field(self):
        assert IntentRecognizer._parse_intent_json('{"foo": "bar"}') is None


@pytest.mark.skip(reason="real LLM required; run manually with API key configured")
class TestRealLLM:
    """真实 LLM 分类(手动跑,mock off)。"""

    @pytest.mark.asyncio
    async def test_real_classify(self, recognizer):
        result = await recognizer.recognize("帮我生成一份电缆装配工艺规程")
        assert result["type"] in (
            IntentType.CREATE_DOCUMENT.value,
            IntentType.GENERATE_DOCUMENT.value,
            IntentType.DRAFT_COMPLETE.value,
        )
