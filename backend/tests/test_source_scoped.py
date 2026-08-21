"""Unit tests for N1 source-scoped retrieval (project working-area filter).

Covers:
- HierarchicalContext.resolve_source_filters three states
- _get_all_documents source_ids filter + cache non-pollution by filtered calls
- KnowledgeSearchService search_materials / find_material_by_code source_ids

All DB access goes through an in-memory SQLite session monkeypatched into
app.database.SessionLocal (never touches the real craftdoc.db).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, Material, CreationProject, MaterialCatalog
from app.services.hierarchical_context import HierarchicalContext
from app.services.knowledge_search import KnowledgeSearchService


@pytest.fixture
def mem_db(monkeypatch):
    """In-memory SQLite session factory patched into app.database.SessionLocal."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    import app.database as db_mod
    monkeypatch.setattr(db_mod, "SessionLocal", factory)
    return factory


@pytest.fixture
def hc(tmp_path, mem_db):
    """HierarchicalContext with tmp data_dir + in-memory DB.

    Creates 3 materials (ids 1/2/3) each with a documents/{id}/ dir so the
    DB-primary path in _get_all_documents picks them up.
    """
    with mem_db() as db:
        for i in (1, 2, 3):
            db.add(Material(id=i, name=f"doc{i}.pdf", material_type="pdf"))
        db.commit()
    for i in (1, 2, 3):
        (tmp_path / str(i)).mkdir()
    return HierarchicalContext(data_dir=tmp_path)


class TestResolveSourceFilters:
    def test_no_project_id_returns_none(self, hc):
        assert hc.resolve_source_filters(None) is None

    def test_missing_project_returns_none(self, hc, mem_db):
        assert hc.resolve_source_filters(999) is None

    def test_empty_material_ids_returns_none(self, hc, mem_db):
        with mem_db() as db:
            db.add(CreationProject(id=1, name="p1", material_ids=[]))
            db.commit()
        assert hc.resolve_source_filters(1) is None

    def test_populated_returns_source_ids(self, hc, mem_db):
        with mem_db() as db:
            db.add(CreationProject(id=2, name="p2", material_ids=[1, 3]))
            db.commit()
        assert hc.resolve_source_filters(2) == {"source_ids": ["1", "3"]}


class TestGetAllDocumentsSourceFilter:
    def test_source_ids_filter(self, hc):
        docs = hc._get_all_documents({"source_ids": ["1", "3"]})
        assert sorted(d["_doc_dir"] for d in docs) == ["1", "3"]

    def test_no_filters_returns_all(self, hc):
        docs = hc._get_all_documents()
        assert sorted(d["_doc_dir"] for d in docs) == ["1", "2", "3"]

    def test_filtered_call_does_not_pollute_cache(self, hc):
        # Fresh instance state: call filtered first, then unfiltered.
        hc.invalidate_cache()
        filtered = hc._get_all_documents({"source_ids": ["1"]})
        assert [d["_doc_dir"] for d in filtered] == ["1"]
        unfiltered = hc._get_all_documents()
        assert sorted(d["_doc_dir"] for d in unfiltered) == ["1", "2", "3"]

    def test_filtered_call_does_not_read_stale_cache(self, hc):
        # Prime the full cache, then a filtered call must NOT hit it.
        hc.invalidate_cache()
        full = hc._get_all_documents()
        assert len(full) == 3
        filtered = hc._get_all_documents({"source_ids": ["2"]})
        assert [d["_doc_dir"] for d in filtered] == ["2"]

    def test_filtered_call_skips_legacy_dir_fallback(self, hc, tmp_path):
        # N6 fix-1: a legacy dir (index.json, no Material row) must NOT leak
        # past a source_ids filter via the file-scan fallback — but it IS
        # visible to unfiltered calls (legacy/DB-less behavior preserved).
        import json as _json

        legacy = tmp_path / "9"
        legacy.mkdir()
        (legacy / "index.json").write_text(
            _json.dumps({"name": "legacy-doc", "_doc_dir": "9"}), encoding="utf-8"
        )

        filtered = hc._get_all_documents({"source_ids": ["1"]})
        assert [d["_doc_dir"] for d in filtered] == ["1"]

        unfiltered = hc._get_all_documents()
        assert sorted(d["_doc_dir"] for d in unfiltered) == ["1", "2", "3", "9"]


class TestKnowledgeSearchSourceFilter:
    @pytest.fixture
    def catalog(self, mem_db):
        with mem_db() as db:
            db.add(MaterialCatalog(id=1, name="螺钉M3", source_doc="1", standard_code="GB1"))
            db.add(MaterialCatalog(id=2, name="螺钉M4", source_doc="2", standard_code="GB2"))
            db.commit()
        return mem_db

    def test_search_materials_filtered(self, catalog):
        svc = KnowledgeSearchService()
        with catalog() as db:
            rows = svc.search_materials(db, "螺钉", source_ids=["1"])
        assert [r["name"] for r in rows] == ["螺钉M3"]

    def test_search_materials_unfiltered(self, catalog):
        svc = KnowledgeSearchService()
        with catalog() as db:
            rows = svc.search_materials(db, "螺钉")
        assert len(rows) == 2

    def test_find_material_by_code_filtered(self, catalog):
        svc = KnowledgeSearchService()
        with catalog() as db:
            assert svc.find_material_by_code(db, "GB1", source_ids=["1"]) is not None
            assert svc.find_material_by_code(db, "GB1", source_ids=["2"]) is None

    def test_find_material_by_code_unfiltered(self, catalog):
        svc = KnowledgeSearchService()
        with catalog() as db:
            assert svc.find_material_by_code(db, "GB2") is not None


class TestProjectSourceIds:
    """ProcessOrchestrator._project_source_ids three states (N3)."""

    @staticmethod
    def _bare_orchestrator():
        # Skip heavy __init__ (agent discovery); only the attrs the method
        # touches are needed.
        from app.agents.orchestrator.orchestrator import ProcessOrchestrator

        orch = ProcessOrchestrator.__new__(ProcessOrchestrator)
        orch._collected_info = {}
        return orch

    def test_no_project_id_returns_none(self):
        orch = self._bare_orchestrator()
        assert orch._project_source_ids() is None

    def test_empty_material_ids_returns_none(self, mem_db):
        with mem_db() as db:
            db.add(CreationProject(id=10, name="p", material_ids=[]))
            db.commit()
        orch = self._bare_orchestrator()
        orch._collected_info = {"context": {"project_id": 10}}
        assert orch._project_source_ids() is None

    def test_populated_material_ids_returns_strs(self, mem_db):
        with mem_db() as db:
            db.add(CreationProject(id=11, name="p", material_ids=[1, 3]))
            db.commit()
        orch = self._bare_orchestrator()
        orch._collected_info = {"context": {"project_id": 11}}
        assert orch._project_source_ids() == ["1", "3"]

    def test_live_query_no_stale_cache(self, mem_db):
        # N6 fix-4: the per-instance cache is gone — the helper is a live
        # query through hc, so a mid-session material_ids edit is reflected
        # on the very next call.
        with mem_db() as db:
            db.add(CreationProject(id=11, name="p", material_ids=[1]))
            db.commit()
        orch = self._bare_orchestrator()
        orch._collected_info = {"context": {"project_id": 11}}
        assert orch._project_source_ids() == ["1"]
        with mem_db() as db:
            db.query(CreationProject).filter(CreationProject.id == 11).delete()
            db.commit()
        assert orch._project_source_ids() is None

    def test_db_failure_fails_soft(self, monkeypatch):
        import app.database as db_mod

        def boom():
            raise RuntimeError("db down")

        monkeypatch.setattr(db_mod, "SessionLocal", boom)
        orch = self._bare_orchestrator()
        orch._collected_info = {"context": {"project_id": 11}}
        assert orch._project_source_ids() is None


class TestSearchKnowledgeGraphSourceFilter:
    """_search_knowledge_graph seed filtering by "{doc_id}::" prefix (N3)."""

    @pytest.fixture
    def fake_kg(self, monkeypatch, hc):
        import types
        import app.services.knowledge_graph as kg_mod
        import app.services.hierarchical_context as hc_mod

        graph = types.SimpleNamespace(nodes={
            "1::辅料A": {"label": "辅料A", "type": "material"},
            "2::辅料A": {"label": "辅料A", "type": "material"},
            "辅料B": {"label": "辅料B", "type": "material"},  # legacy no prefix
        })
        kg = types.SimpleNamespace(
            node_count=3, _graph=graph,
            to_context_text=lambda seed_node_ids, max_tokens: "KGTEXT",
        )
        monkeypatch.setattr(kg_mod, "craft_kg", kg)
        # Deterministic keyword extraction matching the labels above.
        monkeypatch.setattr(hc_mod, "extract_keywords", lambda text: ["辅料A"])
        return kg

    def test_seed_filtered_to_selected_source(self, hc, fake_kg):
        text = hc._search_knowledge_graph("辅料A", 1200, source_ids=["1"])
        assert "KGTEXT" in text

    def test_seed_excluded_when_source_not_selected(self, hc, fake_kg):
        # "辅料A" exists only under docs 1/2; scoping to doc 9 leaves no seed.
        text = hc._search_knowledge_graph("辅料A", 1200, source_ids=["9"])
        assert "KGTEXT" not in text

    def test_no_filter_matches_all(self, hc, fake_kg):
        text = hc._search_knowledge_graph("辅料A", 1200)
        assert "KGTEXT" in text
