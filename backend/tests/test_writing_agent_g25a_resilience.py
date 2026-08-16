"""Unit tests: G25a per-row retry + completeness reporting (N7).

Mocks llm_service.generate_with_messages with scripted side effects per step.
"""
from unittest.mock import AsyncMock

import pytest

from app.agents.functional.writing_agent import WritingAgent


def _agent():
    agent = WritingAgent()
    agent._writing_preferences = None
    agent._profile = None
    return agent


class _Col:
    """Minimal TemplateColumn stand-in: slot key filtering needs key/label."""

    def __init__(self, key, label):
        self.key = key
        self.label = label


def _make_method(agent, n=3):
    """Build a bound-style call into _generate_g25a_per_row_parallel with minimal args."""
    return agent._generate_g25a_per_row_parallel(
        base_system_msg="sys",
        user_parts=["u"],
        unstructured_cols=[_Col("content", "工艺内容")],
        asm={i: {"substeps": []} for i in range(1, n + 1)},
        skel=[f"工序{i}" for i in range(1, n + 1)],
        chapter_code="G25a",
    )


def _ok(step, val="内容"):
    return {"status": "success", "content": f'[{{"row": {step}, "slot": "content", "value": "{val}"}}]', "finish_reason": "stop"}


def _err(msg="Request timed out"):
    return {"status": "error", "error": msg, "error_class": "timeout", "content": "", "finish_reason": None}


class TestPerRowRetry:
    async def test_step_error_twice_then_success_recovers(self, monkeypatch):
        from app.services import llm_service as ls

        # step1 ok; step2: err, err, ok; step3 ok — per-row independence
        calls = {"1": 0, "2": 0, "3": 0}

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex"):
            sys = messages[0]["content"]
            import re
            m = re.search(r"只生成第 (\d+) 道工序", sys)
            step = m.group(1)
            calls[step] += 1
            if step == "2" and calls["2"] <= 2:
                return _err()
            return _ok(int(step))

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)
        content_slots, n, aux, gaps = await _make_method(_agent(), n=3)
        assert calls == {"1": 1, "2": 3, "3": 1}
        rows = {s["row"] for s in content_slots}
        assert rows == {1, 2, 3}
        assert gaps == []

    async def test_step_always_errors_reported_as_gap(self, monkeypatch):
        from app.services import llm_service as ls

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex"):
            import re
            step = re.search(r"只生成第 (\d+) 道工序", messages[0]["content"]).group(1)
            if step == "3":
                return _err()
            return _ok(int(step))

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)
        content_slots, n, aux, gaps = await _make_method(_agent(), n=3)
        assert [g["row"] for g in gaps] == [3]
        assert "工序 3" in gaps[0]["message"]
        assert "工序3" in gaps[0]["message"]  # skeleton name present
        rows = {s["row"] for s in content_slots}
        assert rows == {1, 2}

    async def test_parse_fail_then_valid_json_recovered(self, monkeypatch):
        from app.services import llm_service as ls

        calls = {"1": 0}

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex"):
            import re
            step = re.search(r"只生成第 (\d+) 道工序", messages[0]["content"]).group(1)
            if step == "1":
                calls["1"] += 1
                if calls["1"] == 1:
                    return {"status": "success", "content": "不是JSON", "finish_reason": "stop"}
            return _ok(int(step))

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)
        content_slots, n, aux, gaps = await _make_method(_agent(), n=1)
        assert calls["1"] == 2
        assert gaps == []
        assert content_slots[0]["row"] == 1

    async def test_all_success_no_gaps_no_extra_calls(self, monkeypatch):
        from app.services import llm_service as ls

        collect = AsyncMock(side_effect=None)

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex"):
            import re
            step = re.search(r"只生成第 (\d+) 道工序", messages[0]["content"]).group(1)
            return _ok(int(step))

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)
        content_slots, n, aux, gaps = await _make_method(_agent(), n=4)
        assert gaps == []
        assert len(content_slots) == 4


class TestSubTextFallback:
    """N10: retries exhausted → content falls back to sub_text verbatim."""

    def _make_method_with_subs(self, agent, n, subs_map):
        return agent._generate_g25a_per_row_parallel(
            base_system_msg="sys",
            user_parts=["u"],
            unstructured_cols=[_Col("content", "工艺内容")],
            asm={i: {"substeps": subs_map.get(i, [{"content": f"工序{i}的工步原文"}])} for i in range(1, n + 1)},
            skel=[f"工序{i}" for i in range(1, n + 1)],
            chapter_code="G25a",
        )

    async def test_exhausted_retries_fall_back_to_sub_text(self, monkeypatch):
        from app.services import llm_service as ls

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex"):
            import re
            step = re.search(r"只生成第 (\d+) 道工序", messages[0]["content"]).group(1)
            if step == "2":
                return _err()
            return _ok(int(step))

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)
        agent = _agent()
        content_slots, n, aux, gaps = await self._make_method_with_subs(agent, 2, {
            2: [
                {"content": "将螺柱旋入安装孔"},
                {"content": "用力矩扳手紧固", "material": "螺柱 M5"},
            ],
        })
        # row 2 delivered with fallback content, not empty
        row2 = [s for s in content_slots if s["row"] == 2]
        assert len(row2) == 1
        val = row2[0]["value"]
        assert "（原文直填，待润色）" in val
        assert "2.1 将螺柱旋入安装孔" in val
        assert "2.2 用力矩扳手紧固" in val
        # gap reported as degraded (action-oriented), not "留空"
        assert len(gaps) == 1
        assert "已回退原文直填" in gaps[0]["message"]
        assert "留空" not in gaps[0]["message"]

    async def test_no_source_text_true_gap(self, monkeypatch):
        from app.services import llm_service as ls

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex"):
            return _err()

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)
        agent = _agent()
        content_slots, n, aux, gaps = await self._make_method_with_subs(agent, 1, {
            1: [],  # no substeps → sub_text becomes （原文未提供）
        })
        assert content_slots == []
        assert len(gaps) == 1
        assert "留空" in gaps[0]["message"]
