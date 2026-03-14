"""
RAG 检索 Tool

从工艺知识库检索相关信息
"""
from typing import Dict, Any, Optional, List
from app.agents.core import ToolRegistry
from app.shared.logging import get_logger

logger = get_logger(__name__)


@ToolRegistry.register("rag_retriever")
class RAGRetriever:
    """
    RAG 检索工具

    从工艺知识库（向量数据库）中检索相关信息
    """

    name = "rag_retriever"
    description = "从工艺知识库检索相关的工艺规范、标准、案例等信息"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化 RAG 检索器

        Args:
            config: 配置参数
                - top_k: 返回结果数量（默认5）
                - similarity_threshold: 相似度阈值（默认0.7）
                - rerank_enabled: 是否启用重排序（默认True）
        """
        self.config = config or {}
        self.top_k = self.config.get("top_k", 5)
        self.similarity_threshold = self.config.get("similarity_threshold", 0.7)
        self.rerank_enabled = self.config.get("rerank_enabled", True)

        # 延迟加载 VectorStore
        self._vector_store = None

        logger.info(
            "rag_retriever_initialized",
            top_k=self.top_k,
            similarity_threshold=self.similarity_threshold
        )

    @property
    def vector_store(self):
        """延迟加载 VectorStore"""
        if self._vector_store is None:
            try:
                from app.tools.vector_store import VectorStore
                self._vector_store = VectorStore(self.config)
            except Exception as e:
                logger.error("vector_store_load_failed", error=str(e))
        return self._vector_store

    async def execute(
        self,
        input_data: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行检索

        Args:
            input_data: 检索查询字符串
            context: 执行上下文
                - filters: 过滤条件
                - doc_types: 文档类型过滤

        Returns:
            {
                "success": bool,
                "results": [
                    {
                        "content": str,
                        "metadata": dict,
                        "score": float
                    }
                ],
                "query": str,
                "total": int
            }
        """
        try:
            if not input_data or not isinstance(input_data, str):
                return {
                    "success": False,
                    "error": "查询内容不能为空",
                    "error_code": "INVALID_QUERY"
                }

            # 获取上下文参数
            filters = context.get("filters", {}) if context else {}
            top_k = context.get("top_k", self.top_k) if context else self.top_k

            # 执行检索
            if self.vector_store is None:
                # 返回模拟结果（VectorStore 不可用时）
                return self._mock_search(input_data, top_k)

            # 实际检索
            search_results = await self._search(input_data, filters, top_k)

            logger.info(
                "rag_search_completed",
                query=input_data[:50],
                results_count=len(search_results)
            )

            return {
                "success": True,
                "results": search_results,
                "query": input_data,
                "total": len(search_results)
            }

        except Exception as e:
            logger.error("rag_search_failed", error=str(e), query=input_data[:50])
            return {
                "success": False,
                "error": str(e),
                "error_code": "SEARCH_FAILED"
            }

    async def _search(
        self,
        query: str,
        filters: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        执行实际检索

        Args:
            query: 查询字符串
            filters: 过滤条件
            top_k: 返回数量

        Returns:
            检索结果列表
        """
        # 调用 VectorStore 检索
        results = self.vector_store.search(
            query=query,
            top_k=top_k,
            filters=filters,
            include_metadata=True
        )

        # 格式化结果
        formatted_results = []
        for item in results.get("results", []):
            formatted_results.append({
                "content": item.get("content", ""),
                "metadata": item.get("metadata", {}),
                "score": item.get("score", 0.0)
            })

        return formatted_results

    def _mock_search(self, query: str, top_k: int) -> Dict[str, Any]:
        """
        模拟检索（VectorStore 不可用时）

        Args:
            query: 查询字符串
            top_k: 返回数量

        Returns:
            模拟结果
        """
        return {
            "success": True,
            "results": [
                {
                    "content": f"关于'{query}'的工艺规范参考内容",
                    "metadata": {"source": "mock", "type": "specification"},
                    "score": 0.85
                }
            ],
            "query": query,
            "total": 1,
            "note": "VectorStore 不可用，返回模拟结果"
        }
