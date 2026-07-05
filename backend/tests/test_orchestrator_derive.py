"""Unit tests for Orchestrator derive-strong-node helpers (节点2).

Focus: _slot_items_to_rows + _merge_derived_rows — the static helpers that
convert derived slot-items to row dicts and do original-first merge + 待补.
"""
import pytest
from app.agents.orchestrator.orchestrator import ProcessOrchestrator


class TestSlotItemsToRows:
    def test_group_by_row(self):
        derived = [
            {"row": 1, "slot": "name", "value": "螺钉"},
            {"row": 1, "slot": "qty", "value": "10"},
            {"row": 2, "slot": "name", "value": "垫圈"},
            {"row": 2, "slot": "qty", "value": "20"},
        ]
        rows = ProcessOrchestrator._slot_items_to_rows(derived)
        assert len(rows) == 2
        assert rows[0] == {"name": "螺钉", "qty": "10"}
        assert rows[1] == {"name": "垫圈", "qty": "20"}

    def test_empty(self):
        assert ProcessOrchestrator._slot_items_to_rows([]) == []


class TestMergeDerivedRows:
    def test_original_first_derived_fills_missing(self):
        original = [{"name": "螺钉", "qty": ""}]  # qty empty in original
        derived = [{"name": "螺钉", "qty": "10"}]
        slot_keys = ["name", "qty"]
        merged = ProcessOrchestrator._merge_derived_rows(original, derived, slot_keys)
        assert merged[0]["name"] == "螺钉"  # original kept
        assert merged[0]["qty"] == "10"     # filled from derived

    def test_missing_slot_marked_待补(self):
        original = [{"name": "螺钉"}]  # qty missing entirely
        derived = []
        slot_keys = ["name", "qty", "net_weight"]
        merged = ProcessOrchestrator._merge_derived_rows(original, derived, slot_keys)
        assert merged[0]["name"] == "螺钉"
        assert merged[0]["qty"] == "待补"
        assert merged[0]["net_weight"] == "待补"

    def test_derived_appended_when_more_than_original(self):
        original = [{"name": "螺钉"}]
        derived = [{"name": "垫圈"}, {"name": "卡箍"}]
        slot_keys = ["name"]
        merged = ProcessOrchestrator._merge_derived_rows(original, derived, slot_keys)
        assert len(merged) == 2  # original row + 1 derived (original kept, derived[0] merges into it, derived[1] appends)
        assert merged[0]["name"] == "螺钉"
        assert merged[1]["name"] == "卡箍"

    def test_both_empty(self):
        assert ProcessOrchestrator._merge_derived_rows([], [], ["x"]) == []

    def test_no_slot_keys_no_marker(self):
        original = [{"name": "螺钉"}]
        merged = ProcessOrchestrator._merge_derived_rows(original, [], [])
        assert merged == [{"name": "螺钉"}]
