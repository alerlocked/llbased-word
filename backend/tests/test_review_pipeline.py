"""Unit tests for review_pipeline four-way check (N4)."""
from unittest.mock import AsyncMock

import pytest

from app.services import review_pipeline as rp


def _gen_results(codes=("G1a", "G4a", "G5a", "G10a", "B12a", "G12a", "G14a", "G19a", "G18a", "G22a", "G25a")):
    return {c: {"chapter_title": c, "filled_data": [{"a": "1"}], "warnings": []} for c in codes}


class TestTemplateCheck:
    def test_missing_chapters_detected(self):
        results = _gen_results(codes=("G1a", "G4a"))  # 9 missing
        issues = rp._check_template("assembly_process_cable", results)
        critical = [i for i in issues if i["severity"] == "critical"]
        assert len(critical) == 9
        assert any("G25a" in i["message"] for i in critical)

    def test_complete_no_missing(self):
        issues = rp._check_template("assembly_process_cable", _gen_results())
        assert not any(i["severity"] == "critical" for i in issues)
        assert any("无缺章" in i["message"] for i in issues)

    def test_template_source_tagged(self):
        issues = rp._check_template("assembly_process_cable", {})
        assert all(i["source"] == "template" for i in issues)


class TestQualityCheck:
    def test_empty_and_placeholder_cells_flagged(self):
        results = {
            "G25a": {
                "chapter_title": "装配工艺卡片",
                "filled_data": [{"content": "待补"}, {"content": "  "}, {"content": "ok"}],
                "warnings": [{"row": 2, "message": "工序 2 生成失败，已回退原文直填，建议人工复核"}],
            }
        }
        issues = rp._check_quality(results)
        warns = [i["message"] for i in issues if i["severity"] == "warn"]
        assert any("待补格子" in m for m in warns)
        assert any("已回退原文直填" in m for m in warns)

    def test_clean_chapter_info_only(self):
        issues = rp._check_quality({"G1a": {"filled_data": [{"a": "x"}], "warnings": []}})
        assert not any(i["severity"] == "warn" for i in issues)


class TestDbCheck:
    def test_no_materials_no_issue(self):
        assert rp._check_db({"G1a": {"filled_data": [{"content": "ok"}]}}) == []

    def test_db_down_swallowed(self, monkeypatch):
        def boom():
            raise RuntimeError("db down")

        monkeypatch.setattr("app.database.SessionLocal", boom)
        # must not raise — grounding failure degrades to no-issue
        assert rp._check_db({"G14a": {"filled_data": [{"材料名称": "无水乙醇"}]}}) == []


class TestCoverageCheck:
    async def test_llm_receives_fact_lines_only(self, monkeypatch):
        from app.services import llm_service as ls

        captured = {}

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
            captured["prompt"] = messages[0]["content"]
            captured["tier"] = tier
            return {"status": "success", "content": "对照完成，无缺章。", "finish_reason": "stop"}

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)
        out = await rp._check_coverage("还需要补充吗", ["缺章：G12a（材料定额明细）未生成", "G25a 有 2 个空格子"])
        assert out == "对照完成，无缺章。"
        assert captured["tier"] == "simple"
        assert "禁止基于通识" in captured["prompt"]
        assert "G12a" in captured["prompt"]

    async def test_llm_failure_degrades_gracefully(self, monkeypatch):
        from app.services import llm_service as ls

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
            return {"status": "error", "error": "down", "content": "", "finish_reason": None}

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)
        out = await rp._check_coverage("q", ["fact"])
        assert "机器对照" in out  # graceful degrade message


class TestRunReview:
    async def test_full_flow_with_snapshot_fallback(self, monkeypatch):
        """No structured_results → falls back to state.last_output chapter codes."""
        from app.services import llm_service as ls

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
            return {"status": "success", "content": "按清单回答。", "finish_reason": "stop"}

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)
        state = {"last_output": {"chapters": [{"code": c, "title": "", "rows": 1} for c in ("G1a", "G4a", "G25a")]}}
        result = await rp.run_review("还需要补充吗", project_state=state)
        codes_missing = [i for i in result["issues"] if i["severity"] == "critical"]
        assert len(codes_missing) == 8  # 11 template − 3 snapshot
        assert "审查结果" in result["reply"]
        assert "按清单回答" in result["reply"]
