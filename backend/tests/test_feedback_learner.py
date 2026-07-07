"""
test_feedback_learner.py - FeedbackLearner unit tests (skip_llm deterministic path).
"""
import pytest

from app.services.feedback_learner import FeedbackLearner


async def test_no_edits_returns_empty():
    learner = FeedbackLearner()
    result = await learner.learn_from_edits([], [], skip_llm=True)
    assert result == []


async def test_fallback_repeated_column_induces_one_rule():
    """Same col_key with >=2 identical old→new → one terminology rule, pending review."""
    learner = FeedbackLearner()
    edits = [
        {"col_key": "tool", "col_label": "工具", "old_value": "扳手", "new_value": "扭矩扳手"},
        {"col_key": "tool", "col_label": "工具", "old_value": "扳手", "new_value": "扭矩扳手"},
        {"col_key": "tool", "col_label": "工具", "old_value": "扳手", "new_value": "扭矩扳手"},
    ]
    result = await learner.learn_from_edits(edits, [], skip_llm=True)
    assert len(result) == 1
    rule = result[0]
    assert rule.dimension == "terminology"
    assert rule.source == "feedback_learned"
    assert rule.enabled is False  # pending review
    assert "扭矩扳手" in rule.description
    assert "扳手" in rule.description


async def test_fallback_single_edit_no_rule():
    """A single edit (no repeat) → fallback yields nothing."""
    learner = FeedbackLearner()
    edits = [
        {"col_key": "tool", "col_label": "工具", "old_value": "扳手", "new_value": "扭矩扳手"},
    ]
    result = await learner.learn_from_edits(edits, [], skip_llm=True)
    assert result == []


async def test_llm_bad_json_degrades_gracefully(monkeypatch):
    """LLM returns garbage → fail-soft (degrade to fallback), never raise."""
    async def fake_gen(**kwargs):
        return {"status": "success", "content": "not json at all !!!"}

    import app.services.llm_service as ls
    monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)

    learner = FeedbackLearner()
    edits = [
        {"col_key": "t", "old_value": "a", "new_value": "b"},
        {"col_key": "t", "old_value": "a", "new_value": "b"},
    ]
    result = await learner.learn_from_edits(edits, [], skip_llm=False)
    assert isinstance(result, list)  # bad JSON → LLM [] → fallback (repeat a→b → 1 rule)
    assert len(result) == 1


async def test_llm_status_non_success_returns_fallback(monkeypatch):
    """LLM call failure (status != success) → fallback, no raise."""
    async def fake_gen(**kwargs):
        return {"status": "error", "content": ""}

    import app.services.llm_service as ls
    monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)

    learner = FeedbackLearner()
    # No repeated edits → fallback yields []
    result = await learner.learn_from_edits(
        [{"col_key": "t", "old_value": "a", "new_value": "b"}], [], skip_llm=False,
    )
    assert result == []
