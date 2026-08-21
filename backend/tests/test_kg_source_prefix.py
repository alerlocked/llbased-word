"""Unit tests for N2 source-scoped knowledge ingestion.

Covers:
- build_from_triples source prefix: cross-source param coexistence (fixes
  "后学顶掉先学"), same-source re-learn idempotence, source=None backcompat,
  cross-source edge isolation via expand_context
- extract_and_save source-scoped dedup on material_catalog (same doc_id
  idempotent, different doc_id coexists)

DB access goes through in-memory SQLite (never touches real craftdoc.db).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, MaterialCatalog
from app.services.knowledge_graph import KnowledgeGraph

TRIPLES_36 = [{"s": "M5螺柱", "r": "力矩", "o": "3.6"}]
TRIPLES_42 = [{"s": "M5螺柱", "r": "力矩", "o": "4.2"}]


class TestBuildFromTriplesSourcePrefix:
    def test_two_sources_same_spec_coexist(self):
        """Two docs learn the same spec with different values → both survive."""
        kg = KnowledgeGraph()
        kg.merge_from(KnowledgeGraph.build_from_triples(TRIPLES_36, source="1"))
        kg.merge_from(KnowledgeGraph.build_from_triples(TRIPLES_42, source="2"))
        n1 = kg.get_node("1::M5螺柱_力矩")
        n2 = kg.get_node("2::M5螺柱_力矩")
        assert n1 is not None and n1["label"] == "3.6"
        assert n2 is not None and n2["label"] == "4.2"
        # Spec nodes also prefixed and both present, labels unprefixed
        assert kg.get_node("1::M5螺柱")["label"] == "M5螺柱"
        assert kg.get_node("2::M5螺柱")["label"] == "M5螺柱"

    def test_same_source_relearn_idempotent(self):
        """Re-learning the same doc merges to the same ids → nothing added."""
        kg = KnowledgeGraph()
        kg.merge_from(KnowledgeGraph.build_from_triples(TRIPLES_36, source="1"))
        before = (kg.node_count, kg._graph.number_of_edges())
        kg.merge_from(KnowledgeGraph.build_from_triples(TRIPLES_36, source="1"))
        after = (kg.node_count, kg._graph.number_of_edges())
        assert before == after

    def test_source_none_backcompat(self):
        """source=None produces legacy unprefixed ids."""
        kg = KnowledgeGraph.build_from_triples(TRIPLES_36)
        assert kg.get_node("M5螺柱_力矩") is not None
        assert all(not nid.startswith(("1::", "2::")) for nid in kg._graph.nodes)

    def test_cross_source_edge_isolation(self):
        """Expanding from a "1::" seed never reaches "2::" nodes."""
        kg = KnowledgeGraph()
        t1 = [
            {"s": "M5螺柱", "r": "力矩", "o": "3.6"},
            {"s": "装配", "r": "下一步", "o": "检验"},
        ]
        kg.merge_from(KnowledgeGraph.build_from_triples(t1, source="1"))
        kg.merge_from(KnowledgeGraph.build_from_triples(TRIPLES_42, source="2"))
        ctx = kg.expand_context(["1::M5螺柱"])
        ids = {c["id"] for c in ctx}
        assert ids  # something reachable within source 1
        assert all(not i.startswith("2::") for i in ids)


@pytest.fixture
def mem_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return factory


class TestExtractAndSaveSourceScopedDedup:
    @pytest.fixture
    def extractor(self, monkeypatch):
        from app.services.knowledge_extractor import KnowledgeExtractor
        ex = KnowledgeExtractor()

        def fake_extract(doc_id: str) -> dict:
            return {
                "doc_id": doc_id,
                "materials": [{"name": "螺钉M3", "model": "GB1", "source_doc": doc_id}],
                "tools": [],
                "process_steps": [],
                "relations": {},
            }

        monkeypatch.setattr(ex, "extract_from_doc", fake_extract)
        return ex

    def test_same_doc_reextract_no_duplicate(self, extractor, mem_session):
        with mem_session() as db:
            extractor.extract_and_save("1", db)
            db.commit()
            extractor.extract_and_save("1", db)
            db.commit()
            rows = db.query(MaterialCatalog).filter_by(name="螺钉M3").all()
        assert len(rows) == 1

    def test_different_doc_same_name_model_coexist(self, extractor, mem_session):
        with mem_session() as db:
            extractor.extract_and_save("1", db)
            db.commit()
            extractor.extract_and_save("2", db)
            db.commit()
            rows = db.query(MaterialCatalog).filter_by(name="螺钉M3").all()
        assert sorted(r.source_doc for r in rows) == ["1", "2"]
