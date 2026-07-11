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


from unittest.mock import MagicMock


class TestEnrichNamesFromCatalog:
    """_enrich_names_from_catalog (节点2): post-merge catalog enrichment for
    G18a — overwrite misaligned/待补 names with exact catalog lookup."""

    def _patch_catalog(self, monkeypatch, code_to_name, db_raises=False):
        """Patch SessionLocal + KnowledgeSearchService.find_material_by_code."""
        fake_db = MagicMock()
        fake_db.close = MagicMock()

        def fake_sessionlocal():
            if db_raises:
                raise RuntimeError("db down")
            return fake_db

        monkeypatch.setattr("app.database.SessionLocal", fake_sessionlocal)

        def fake_find(self_, db, code):
            name = code_to_name.get(code)
            return {"name": name} if name else None

        monkeypatch.setattr(
            "app.services.knowledge_search.KnowledgeSearchService.find_material_by_code",
            fake_find,
        )
        return fake_db

    def _run(self, rows):
        ProcessOrchestrator._enrich_names_from_catalog(
            MagicMock(), rows, "part_code", "part_name", "G18a"
        )

    def test_overwrites_misaligned_name(self, monkeypatch):
        self._patch_catalog(monkeypatch, {"KA6-0-KZD": "六舱"})
        rows = [{"part_code": "KA6-0-KZD", "part_name": "行程延时开关组合"}]
        self._run(rows)
        assert rows[0]["part_name"] == "六舱"  # catalog overwrites misaligned value

    def test_fills_待补_slot(self, monkeypatch):
        self._patch_catalog(monkeypatch, {"KA6-20-KZD": "尾焰挡板组件"})
        rows = [{"part_code": "KA6-20-KZD", "part_name": "待补"}]
        self._run(rows)
        assert rows[0]["part_name"] == "尾焰挡板组件"

    def test_keeps_name_on_catalog_miss(self, monkeypatch):
        self._patch_catalog(monkeypatch, {})  # catalog has nothing
        rows = [{"part_code": "UNKNOWN-1", "part_name": "某名称"}]
        self._run(rows)
        assert rows[0]["part_name"] == "某名称"  # original kept on miss

    def test_skips_empty_and_待补_code(self, monkeypatch):
        self._patch_catalog(monkeypatch, {"KA6-0-KZD": "六舱"})
        rows = [
            {"part_code": "", "part_name": "无代号"},
            {"part_code": "待补", "part_name": "代号待补"},
            {"part_code": "KA6-0-KZD", "part_name": "待补"},
        ]
        self._run(rows)
        assert rows[0]["part_name"] == "无代号"    # empty code untouched
        assert rows[1]["part_name"] == "代号待补"   # 待补 code untouched
        assert rows[2]["part_name"] == "六舱"       # real code enriched

    def test_empty_rows_noop(self, monkeypatch):
        self._patch_catalog(monkeypatch, {"KA6-0-KZD": "六舱"})
        rows = []
        self._run(rows)  # must not raise

    def test_db_failure_does_not_raise(self, monkeypatch):
        self._patch_catalog(monkeypatch, {}, db_raises=True)
        rows = [{"part_code": "KA6-0-KZD", "part_name": "原值"}]
        self._run(rows)  # SessionLocal raises inside, swallowed
        assert rows[0]["part_name"] == "原值"  # unchanged
