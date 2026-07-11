"""Unit tests for KnowledgeSearchService.find_material_by_code (节点1).

Focus: exact standard_code lookup — zero false-match (unlike search_materials'
LIKE, which would match KA6-0-KZD against KA6-011-KZD). Used by G18a part_name
enrichment to fix the derive misalignment + 待补.
"""
from unittest.mock import MagicMock

from app.services.knowledge_search import KnowledgeSearchService


def _mock_db(first_row=None):
    """Build a db mock where db.query(...).filter(...).first() -> first_row."""
    db = MagicMock()
    filt = MagicMock()
    filt.first.return_value = first_row
    db.query.return_value.filter.return_value = filt
    return db


class TestFindMaterialByCode:
    def test_exact_hit_returns_dict(self, monkeypatch):
        svc = KnowledgeSearchService()
        monkeypatch.setattr(
            svc, "_material_to_dict",
            lambda r: {"name": "尾焰挡板组件", "standard_code": "KA6-20-KZD"},
        )
        db = _mock_db(first_row=MagicMock(name="row"))
        result = svc.find_material_by_code(db, "KA6-20-KZD")
        assert result == {"name": "尾焰挡板组件", "standard_code": "KA6-20-KZD"}
        db.query.return_value.filter.assert_called_once()
        db.query.return_value.filter.return_value.first.assert_called_once()

    def test_empty_code_returns_none_without_query(self):
        svc = KnowledgeSearchService()
        db = _mock_db()
        assert svc.find_material_by_code(db, "") is None
        assert svc.find_material_by_code(db, None) is None
        assert svc.find_material_by_code(db, "   ") is None
        db.query.assert_not_called()  # short-circuit before hitting the DB

    def test_not_found_returns_none(self):
        svc = KnowledgeSearchService()
        db = _mock_db(first_row=None)
        assert svc.find_material_by_code(db, "UNKNOWN-1") is None

    def test_strips_whitespace_then_queries(self, monkeypatch):
        svc = KnowledgeSearchService()
        monkeypatch.setattr(svc, "_material_to_dict", lambda r: {"name": "六舱"})
        db = _mock_db(first_row=MagicMock(name="row"))
        result = svc.find_material_by_code(db, "  KA6-0-KZD  ")
        assert result == {"name": "六舱"}
        db.query.return_value.filter.return_value.first.assert_called_once()
