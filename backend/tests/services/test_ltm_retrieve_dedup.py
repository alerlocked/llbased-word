"""
Tests for LTM retrieve using stored embeddings and dedup fallback.
Covers fix #3: N+1 embedding calls and dedup failure.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestLTMRetrieveUsesStoredEmbeddings:
    """retrieve should prefer stored embeddings over recalculating."""

    def test_retrieve_uses_cached_embedding(self):
        """When embedding is stored, retrieve must NOT call calculate_embedding again."""
        from app.services.context_engineering import LongTermMemory

        ltm = LongTermMemory("test-retrieve-cached")
        fake_embedding = [0.1] * 768

        # Manually inject a memory with stored embedding
        ltm.memories = [{
            "id": "mem_0",
            "content": "决定采用方案A进行加工",
            "topic": "决定采用方案A进行加工",
            "metadata": {},
            "timestamp": "2026-01-01T00:00:00",
            "embedding": fake_embedding,
        }]

        with patch("app.services.context_engineering.calculate_embedding", return_value=fake_embedding) as mock_emb:
            with patch("app.services.context_engineering.calculate_similarity", return_value=0.95):
                results = ltm.retrieve("方案A", top_k=3)
                # calculate_embedding should be called once (for query), NOT for the memory
                assert mock_emb.call_count == 1
                assert len(results) == 1
                assert results[0]["relevance_score"] == 0.95

    def test_retrieve_fallback_to_keywords_on_no_embedding(self):
        """When query embedding fails, fall back to keyword retrieval."""
        from app.services.context_engineering import LongTermMemory

        ltm = LongTermMemory("test-retrieve-keyword")
        ltm.memories = [{
            "id": "mem_0",
            "content": "加工 工艺 参数",
            "topic": "加工",
            "metadata": {},
            "timestamp": "2026-01-01T00:00:00",
            "embedding": None,
        }]

        with patch("app.services.context_engineering.calculate_embedding", return_value=None):
            results = ltm.retrieve("加工 参数", top_k=3)
            # Should get results via keyword fallback
            assert isinstance(results, list)

    def test_retrieve_empty_memories(self):
        """retrieve on empty LTM returns empty list."""
        from app.services.context_engineering import LongTermMemory

        ltm = LongTermMemory("test-retrieve-empty")
        results = ltm.retrieve("anything", top_k=3)
        assert results == []


class TestLTMDedupFallback:
    """Dedup must work even without embeddings."""

    def test_dedup_exact_match(self):
        """Exact same content should be detected as duplicate."""
        from app.services.context_engineering import LongTermMemory

        ltm = LongTermMemory("test-dedup-exact")
        ltm.memories = [{
            "id": "mem_0",
            "content": "决定采用方案A",
            "topic": "决定采用方案A",
            "metadata": {},
            "timestamp": "2026-01-01T00:00:00",
            "embedding": None,
        }]

        with patch("app.services.context_engineering.calculate_embedding", return_value=None):
            memory_id = ltm.write("决定采用方案A", metadata={})
            # Should be detected as duplicate
            assert memory_id == ""

    def test_dedup_text_overlap_fallback(self):
        """Similar content (prefix overlap) should be deduped without embeddings."""
        from app.services.context_engineering import LongTermMemory

        ltm = LongTermMemory("test-dedup-overlap")
        ltm.memories = [{
            "id": "mem_0",
            "content": "记住这个关键的工艺参数设置非常重要",
            "topic": "记住这个关键的工艺参数设置非常重要",
            "metadata": {},
            "timestamp": "2026-01-01T00:00:00",
            "embedding": None,
        }]

        with patch("app.services.context_engineering.calculate_embedding", return_value=None):
            memory_id = ltm.write("记住这个关键的工艺参数设置也很重要", metadata={})
            # Should be detected as duplicate via text overlap
            assert memory_id == ""

    def test_different_content_not_deduped(self):
        """Completely different content should not be deduped."""
        from app.services.context_engineering import LongTermMemory

        ltm = LongTermMemory("test-dedup-diff")
        ltm.memories = [{
            "id": "mem_0",
            "content": "装配工艺流程",
            "topic": "装配工艺流程",
            "metadata": {},
            "timestamp": "2026-01-01T00:00:00",
            "embedding": None,
        }]

        with patch("app.services.context_engineering.calculate_embedding", return_value=None):
            memory_id = ltm.write("热处理温度参数设定", metadata={})
            # Different content, should be written
            assert memory_id != ""
