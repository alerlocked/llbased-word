"""Unit tests for N1 source-scoped retrieval (project working-area filter).

Covers:
- HierarchicalContext._resolve_source_filters three states
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
        assert hc._resolve_source_filters(None) is None

    def test_missing_project_returns_none(self, hc, mem_db):
        assert hc._resolve_source_filters(999) is None

    def test_empty_material_ids_returns_none(self, hc, mem_db):
        with mem_db() as db:
            db.add(CreationProject(id=1, name="p1", material_ids=[]))
            db.commit()
        assert hc._resolve_source_filters(1) is None

    def test_populated_returns_source_ids(self, hc, mem_db):
        with mem_db() as db:
            db.add(CreationProject(id=2, name="p2", material_ids=[1, 3]))
            db.commit()
        assert hc._resolve_source_filters(2) == {"source_ids": ["1", "3"]}


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
