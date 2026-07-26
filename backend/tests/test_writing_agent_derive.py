"""Unit tests for WritingAgent derivation helpers (倒推强节点 节点1).

Focus: _provenance_filter — anti-fabrication guard that drops derived items
whose value cannot be traced in upstream text.
"""
import pytest
from unittest.mock import MagicMock

from app.agents.functional.writing_agent import WritingAgent


def _call_filter(parsed, upstream, chapter_type):
    # _provenance_filter doesn't use self state — pass a mock to avoid heavy init
    return WritingAgent._provenance_filter(MagicMock(), parsed, upstream, chapter_type)


class TestProvenanceFilter:
    """倒推条目必须能在 upstream 找出处，否则丢弃（宁可少不可假）。"""

    def test_single_keeps_traced_drops_untraced(self):
        upstream = "螺钉 力矩 3.6N·m 焊接工艺 装配工序"
        parsed = [
            {"row": 1, "slot": "name", "value": "螺钉"},      # traced → keep
            {"row": 2, "slot": "name", "value": "虚构工具XYZ"},  # fabricated → drop
            {"row": 3, "slot": "name", "value": "焊接"},        # traced → keep
        ]
        result = _call_filter(parsed, upstream, "single_row_list")
        values = [r["value"] for r in result]
        assert "螺钉" in values
        assert "焊接" in values
        assert "虚构工具XYZ" not in values
        assert len(result) == 2

    def test_single_keeps_empty_and_missing_marker(self):
        upstream = "焊接"
        parsed = [
            {"row": 1, "slot": "name", "value": "焊接"},       # traced
            {"row": 2, "slot": "name", "value": ""},           # empty → keep
            {"row": 3, "slot": "name", "value": "待补"},        # marker → keep
        ]
        result = _call_filter(parsed, upstream, "single_row_list")
        assert len(result) == 3

    def test_dual_filters_both_sides(self):
        upstream = "扳手 卡尺 螺钉"
        parsed = {
            "left": [{"name": "扳手"}, {"name": "虚构工具"}],
            "right": [{"name": "卡尺"}, {"name": "虚构量具"}],
        }
        result = _call_filter(parsed, upstream, "dual_list")
        assert len(result["left"]) == 1
        assert result["left"][0]["name"] == "扳手"
        assert len(result["right"]) == 1
        assert result["right"][0]["name"] == "卡尺"

    def test_no_upstream_keeps_all(self):
        # safety: no upstream text to check against → keep everything
        parsed = [{"row": 1, "slot": "name", "value": "anything"}]
        result = _call_filter(parsed, "", "single_row_list")
        assert len(result) == 1

    def test_token_match_keeps_partial(self):
        # value split into tokens; any len>=2 token in upstream → keep
        upstream = "Q235 钢材"
        parsed = [{"row": 1, "slot": "material", "value": "Q235 钢材"}]
        result = _call_filter(parsed, upstream, "single_row_list")
        assert len(result) == 1


class TestG14aInjectG25aAuxMaterials:
    """N4: G14a derive must see ALL G25a aux_materials, not just seq 1.

    The 8000-char upstream-text truncation can drop late G25a rows' aux entries,
    so _inject_g25a_aux_for_g14a re-appends the full non-empty aux_materials
    column. Provenance_filter (substring check) then passes every aux material.
    """

    def _inject(self, upstream_text, upstream, chapter_code="G14a"):
        return WritingAgent._inject_g25a_aux_for_g14a(
            upstream_text, upstream, chapter_code
        )

    def test_all_aux_materials_appended(self):
        # G25a filled_data carries multiple aux materials across rows
        upstream = {"G25a": {"filled_data": [
            {"step_no": 1, "aux_materials": "无水乙醇"},
            {"step_no": 2, "aux_materials": "7804润滑脂"},
            {"step_no": 3, "aux_materials": "乐泰222"},
            {"step_no": 4, "aux_materials": "GD414"},
        ]}}
        result = self._inject("工序内容...", upstream)
        # every aux material must appear (provenance filter will then keep them)
        for aux in ("无水乙醇", "7804润滑脂", "乐泰222", "GD414"):
            assert aux in result
        assert "## G25a 辅助材料列(全)" in result

    def test_empty_aux_rows_skipped(self):
        # rows with blank/missing aux_materials must not contribute
        upstream = {"G25a": {"filled_data": [
            {"aux_materials": "白棉布"},
            {"aux_materials": ""},
            {"aux_materials": None},
            {},  # no key at all
            {"aux_materials": "无水乙醇"},
        ]}}
        result = self._inject("base", upstream)
        assert "白棉布" in result
        assert "无水乙醇" in result
        # only 2 numbered entries (blanks dropped): no "3." item appears
        assert "\n1. 白棉布" in result
        assert "\n2. 无水乙醇" in result
        assert "3." not in result.split("## G25a 辅助材料列(全)")[1]

    def test_non_g14a_untouched(self):
        # only G14a triggers injection; other chapters get text back as-is
        upstream = {"G25a": {"filled_data": [{"aux_materials": "无水乙醇"}]}}
        result = self._inject("base", upstream, chapter_code="G18a")
        assert result == "base"

    def test_no_g25a_or_empty_returns_as_is(self):
        # no G25a upstream → nothing to inject → original text returned
        assert self._inject("base", {}) == "base"
        assert self._inject("base", {"G25a": {}}) == "base"
        assert self._inject("base", {"G25a": {"filled_data": []}}) == "base"
        assert self._inject("base", {"G25a": {"filled_data": [{"aux_materials": ""}]}}) == "base"

    def test_provenance_passes_after_inject(self):
        # end-to-end-ish: injected text must let provenance_filter keep all aux
        upstream = {"G25a": {"filled_data": [
            {"aux_materials": "无水乙醇"},
            {"aux_materials": "GD414"},
        ]}}
        injected = self._inject("base", upstream)
        parsed = [
            {"row": 1, "slot": "material_desc", "value": "无水乙醇"},
            {"row": 2, "slot": "material_desc", "value": "GD414"},
        ]
        result = _call_filter(parsed, injected, "single_row_list")
        assert len(result) == 2  # both survive provenance (no drop)
