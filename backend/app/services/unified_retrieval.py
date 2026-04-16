"""
UnifiedRetrievalService - Unified entry point for cross-source retrieval.

Combines results from memory, knowledge base (indexed documents), and
user profile into a single ranked context for LLM injection.
"""
from typing import Any, Dict, List, Optional

from app.shared.logging import get_logger
from app.services.indexing_service import IndexingService
from app.services.memory_service import MemoryService
from app.config import settings

logger = get_logger(__name__)


class UnifiedRetrievalService:
    """
    Unified retrieval across memory, knowledge, and profile sources.

    Provides a single `retrieve()` method that fans out to all sources,
    merges results by relevance, and respects a token budget.
    """

    def __init__(
        self,
        memory_dir: Optional[str] = None,
        data_dir: Optional[str] = None,
    ):
        self._memory_service: Optional[MemoryService] = None
        self._memory_dir = memory_dir
        self._indexing_service: Optional[IndexingService] = None
        self._data_dir = data_dir

    @property
    def memory_service(self) -> MemoryService:
        if self._memory_service is None:
            mem_dir = self._memory_dir or str(settings.DATA_DIR / "memory")
            self._memory_service = MemoryService(mem_dir)
        return self._memory_service

    @property
    def indexing_service(self) -> IndexingService:
        if self._indexing_service is None:
            self._indexing_service = IndexingService(
                data_dir=self._data_dir or settings.EXPORTS_VLM_DIR
            )
        return self._indexing_service

    async def retrieve(
        self,
        query: str,
        max_tokens: int = 4000,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve relevant context from multiple sources.

        Args:
            query: User query or task description
            max_tokens: Total token budget across all sources
            sources: Optional filter for sources to use.
                     Options: "memory", "knowledge". Default: all.

        Returns:
            Dict with "results" (list), "total_tokens", and "source_counts"
        """
        sources = sources or ["memory", "knowledge"]

        # Allocate token budget evenly across sources
        per_source_budget = max_tokens // max(len(sources), 1)

        all_results: List[Dict[str, Any]] = []
        source_counts: Dict[str, int] = {}

        if "memory" in sources:
            memory_text = self.memory_service.load_relevant_memory(
                query=query, max_tokens=per_source_budget, top_k=3
            )
            if memory_text:
                all_results.append({
                    "content": memory_text,
                    "source": "memory",
                    "relevance_score": 1.0,
                })
                source_counts["memory"] = 1

        if "knowledge" in sources:
            try:
                kb_result = await self.indexing_service.search(
                    query=query, top_k=5
                )
                if kb_result.get("success"):
                    for item in kb_result.get("results", []):
                        all_results.append({
                            "content": item.get("text", ""),
                            "source": f"knowledge:{item.get('metadata', {}).get('source', '')}",
                            "relevance_score": item.get("similarity", 0.0),
                        })
                    source_counts["knowledge"] = len(kb_result.get("results", []))
            except Exception as e:
                logger.error("knowledge_retrieval_failed", error=str(e))

        # Sort by relevance and truncate to token budget
        all_results.sort(key=lambda r: r.get("relevance_score", 0.0), reverse=True)
        all_results = self._truncate_results(all_results, max_tokens)

        total_tokens = sum(r.get("token_count", 0) for r in all_results)

        return {
            "results": all_results,
            "total_tokens": total_tokens,
            "source_counts": source_counts,
        }

    def _truncate_results(
        self, results: List[Dict[str, Any]], max_tokens: int
    ) -> List[Dict[str, Any]]:
        """Truncate results to fit within token budget."""
        truncated: List[Dict[str, Any]] = []
        used = 0
        for r in results:
            content = r.get("content", "")
            tokens = self._estimate_tokens(content)
            if used + tokens <= max_tokens:
                r["token_count"] = tokens
                truncated.append(r)
                used += tokens
            elif max_tokens - used > 100:
                remaining = max_tokens - used
                r["content"] = content[:remaining * 2]
                r["token_count"] = remaining
                truncated.append(r)
                break
            else:
                break
        return truncated

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        chinese = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other = len(text) - chinese
        return int(chinese / 1.5 + other / 4) + 1
