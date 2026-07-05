"""Unit tests for HierarchicalContext model/specialty 检索穿透 (节点4)."""
import inspect
import pytest

from app.services.hierarchical_context import HierarchicalContext


@pytest.fixture
def hc(tmp_path, monkeypatch):
    """HierarchicalContext with a tmp data_dir (no real DB/docs needed)."""
    return HierarchicalContext(data_dir=tmp_path)


class TestBuildDocDictDimensions:
    def test_carries_model_specialty(self, hc):
        doc = hc._build_doc_dict("1", "test.pdf", model="XX-1", specialty="welding")
        assert doc["model"] == "XX-1"
        assert doc["specialty"] == "welding"
        assert doc["name"] == "test.pdf"
        assert doc["_doc_dir"] == "1"

    def test_defaults_none(self, hc):
        doc = hc._build_doc_dict("2", "x.pdf")
        assert doc["model"] is None
        assert doc["specialty"] is None


class TestFilterSignatures:
    """_get_all_documents / search_tables / global_keyword_search accept filters."""

    def test_get_all_documents_has_filters_param(self):
        sig = inspect.signature(HierarchicalContext._get_all_documents)
        assert "filters" in sig.parameters

    def test_search_tables_has_filters_param(self):
        sig = inspect.signature(HierarchicalContext.search_tables)
        assert "filters" in sig.parameters

    def test_global_keyword_search_has_filters_param(self):
        sig = inspect.signature(HierarchicalContext.global_keyword_search)
        assert "filters" in sig.parameters
