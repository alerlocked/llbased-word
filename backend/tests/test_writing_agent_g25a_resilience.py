import json
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

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
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

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
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

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
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

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
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

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
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

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
            return _err()

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)
        agent = _agent()
        content_slots, n, aux, gaps = await self._make_method_with_subs(agent, 1, {
            1: [],  # no substeps → sub_text becomes （原文未提供）
        })
        assert content_slots == []
        assert len(gaps) == 1
        assert "留空" in gaps[0]["message"]

    async def test_inspection_only_row_reported_as_gap(self, monkeypatch):
        """F3: row with inspection filled but content empty = gap (old any-slot
        check let it slip through silently)."""
        from app.services import llm_service as ls

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
            import re
            step = re.search(r"只生成第 (\d+) 道工序", messages[0]["content"]).group(1)
            if step == "1":
                return {
                    "status": "success",
                    "content": json.dumps([
                        {"row": 1, "slot": "inspection", "value": "检查密封性"},
                        {"row": 1, "slot": "content", "value": ""},
                    ]),
                    "finish_reason": "stop",
                }
            return _ok(int(step))

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)
        agent = _agent()
        content_slots, n, aux, gaps = await self._make_method_with_subs(agent, 2, {})
        assert [g["row"] for g in gaps] == [1]
        assert "生成失败" in gaps[0]["message"]

    async def test_degraded_flag_detection_not_text_sniff(self, monkeypatch):
        """F8b: degraded rows detected via flag, not marker-string sniffing."""
        from app.services import llm_service as ls

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
            import re
            step = re.search(r"只生成第 (\d+) 道工序", messages[0]["content"]).group(1)
            if step == "1":
                return _ok(int(step))
            return _err()

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)
        agent = _agent()
        content_slots, n, aux, gaps = await self._make_method_with_subs(agent, 2, {})
        # row 2 fell back: slot carries degraded=True
        row2 = [s for s in content_slots if s["row"] == 2]
        assert row2 and row2[0].get("degraded") is True
        assert [g["row"] for g in gaps] == [2]
        assert "已回退原文直填" in gaps[0]["message"]


class TestSingleLayerRetry:
    """F5: gen_one owns the retry budget; inner transport does single-shot."""

    async def test_gen_one_passes_zero_retries(self, monkeypatch):
        from app.services import llm_service as ls

        seen_kwargs = {}

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
            import re
            step = re.search(r"只生成第 (\d+) 道工序", messages[0]["content"]).group(1)
            seen_kwargs[int(step)] = max_retries
            return _ok(int(step))

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)
        await _make_method(_agent(), n=2)
        assert seen_kwargs == {1: 0, 2: 0}  # inner layer disabled for per-row

    async def test_row_retry_count_is_three_not_nine(self, monkeypatch):
        from app.services import llm_service as ls

        calls = {"1": 0}

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
            calls["1"] += 1
            return _err()

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)
        await _make_method(_agent(), n=1)
        assert calls["1"] == 3  # outer loop only — no 3×3 multiplication


class TestContentNamePrefix:
    """Programmatic "{name}：" prefix on content slots (prompt cannot hold)."""

    def _make_method_with_skel(self, agent, n, skel):
        return agent._generate_g25a_per_row_parallel(
            base_system_msg="sys",
            user_parts=["u"],
            unstructured_cols=[_Col("content", "工艺内容")],
            asm={i: {"substeps": [{"content": f"工序{i}的工步原文"}]} for i in range(1, n + 1)},
            skel=skel,
            chapter_code="G25a",
        )

    @staticmethod
    def _mock_llm(monkeypatch, value_for):
        """value_for: callable(step:int) -> content value string (or None → err)."""
        from app.services import llm_service as ls

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
            import re
            step = int(re.search(r"只生成第 (\d+) 道工序", messages[0]["content"]).group(1))
            val = value_for(step)
            if val is None:
                return _err()
            return {
                "status": "success",
                "content": json.dumps([{"row": step, "slot": "content", "value": val}]),
                "finish_reason": "stop",
            }

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)

    async def test_prefix_added_when_llm_omits_it(self, monkeypatch):
        self._mock_llm(monkeypatch, lambda s: "1.1 内容")
        content_slots, n, aux, gaps = await self._make_method_with_skel(_agent(), 1, ["工序1"])
        assert content_slots[0]["value"] == "工序1：\n1.1 内容"

    async def test_no_double_prefix_fullwidth(self, monkeypatch):
        self._mock_llm(monkeypatch, lambda s: "工序1：\n1.1 内容")
        content_slots, *_ = await self._make_method_with_skel(_agent(), 1, ["工序1"])
        assert content_slots[0]["value"] == "工序1：\n1.1 内容"

    async def test_no_double_prefix_halfwidth_with_whitespace(self, monkeypatch):
        self._mock_llm(monkeypatch, lambda s: " 工序1: 1.1 内容")
        content_slots, *_ = await self._make_method_with_skel(_agent(), 1, ["工序1"])
        assert content_slots[0]["value"] == "工序1：\n1.1 内容"

    async def test_fallback_content_gets_prefix(self, monkeypatch):
        self._mock_llm(monkeypatch, lambda s: None if s == 2 else "内容")
        content_slots, n, aux, gaps = await self._make_method_with_skel(
            _agent(), 2, ["工序1", "工序2"]
        )
        row2 = [s for s in content_slots if s["row"] == 2][0]
        assert row2["value"].startswith("工序2：\n")
        assert "（原文直填，待润色）" in row2["value"]
        assert row2.get("degraded") is True

    async def test_empty_name_no_prefix(self, monkeypatch):
        self._mock_llm(monkeypatch, lambda s: "1.1 内容")
        content_slots, *_ = await self._make_method_with_skel(_agent(), 1, [""])
        assert content_slots[0]["value"] == "1.1 内容"

    async def test_prefix_plus_renumber_coexist(self, monkeypatch):
        self._mock_llm(monkeypatch, lambda s: "1.1 xxx\n1.2 yyy" if s == 2 else "内容")
        content_slots, *_ = await self._make_method_with_skel(
            _agent(), 2, ["工序1", "工序2"]
        )
        row2 = [s for s in content_slots if s["row"] == 2][0]
        assert row2["value"] == "工序2：\n2.1 xxx\n2.2 yyy"
