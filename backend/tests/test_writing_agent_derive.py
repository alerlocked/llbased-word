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
