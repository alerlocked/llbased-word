"""
Tests for async safety in LTM persist and MemoryService ChromaDB indexing.
Covers fix #2: async event loop bugs.
"""
import pytest
from pathlib import Path
import tempfile


class TestLTMPersistAsyncSafe:
    """LongTermMemory._persist_to_chroma must not deadlock in async context."""

    def test_write_in_sync_context_no_crash(self):
        """Writing LTM in sync context should not raise."""
        from app.services.context_engineering import LongTermMemory

        ltm = LongTermMemory("test-async-sync")
        # calculate_embedding will return None (no API key), which is fine
        # We just verify no crash from async code
        memory_id = ltm.write("test content for sync write", metadata={"test": True})
        # ID may be empty if embedding-based dedup skips it, but no crash
        assert isinstance(memory_id, str)

    @pytest.mark.asyncio
    async def test_write_in_async_context_no_deadlock(self):
        """Writing LTM inside a running event loop must not deadlock."""
        from app.services.context_engineering import LongTermMemory

        ltm = LongTermMemory("test-async-loop")
        memory_id = ltm.write("test content in async", metadata={"test": True})
        assert isinstance(memory_id, str)


class TestMemoryServiceIndexAsyncSafe:
    """MemoryService.index_memories_to_chroma must not deadlock."""

    def test_index_in_sync_context(self):
        """index_memories_to_chroma in sync context should work."""
        from app.services.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(tmp)
            # Create a memory file
            svc.save_summary("session-1", "test summary content")
            result = svc.index_memories_to_chroma()
            # May fail if VectorStore/ChromaDB not available, but must not crash
            assert "indexed" in result

    @pytest.mark.asyncio
    async def test_index_in_async_context(self):
        """index_memories_to_chroma inside running event loop must not deadlock."""
        from app.services.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(tmp)
            svc.save_summary("session-2", "test summary in async")
            # Must complete within reasonable time (no deadlock)
            result = svc.index_memories_to_chroma()
            assert "indexed" in result
