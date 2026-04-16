"""
工艺文件辅助编辑系统 - BGE-Rerank模型集成
Identity reranker: preserves original order with normalized scores
"""
from typing import Dict, Any, Optional, List

from app.shared.logging import get_logger

logger = get_logger(__name__)


class BGERerankModel:
    """
    BGE-Rerank模型集成

    提供BGE-Rerank模型的本地重排序接口，
    用于检索结果的精排序
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化BGE-Rerank模型

        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.model_path = self.config.get("model_path", "./models/bge-reranker-large")
        self.device = self.config.get("device", "cuda:0")
        self.use_gpu = self.config.get("use_gpu", True)
        self.max_sequence_length = self.config.get("max_sequence_length", 512)
        self.batch_size = self.config.get("batch_size", 16)

        # 模型状态
        self.model_loaded = False
        self.model_instance = None

        logger.info(
            "bge_rerank_model_initialized",
            model_path=self.model_path,
            device=self.device,
            use_gpu=self.use_gpu
        )

    async def load_model(self) -> bool:
        """
        Initialize identity reranker (no external model needed).

        Returns:
            Always True
        """
        if self.model_loaded:
            logger.info("bge_rerank_model_already_loaded")
            return True

        self.model_loaded = True
        logger.info("bge_rerank_identity_reranker_initialized")
        return True

    async def rerank_results(self, query: str, documents: List[str]) -> Dict[str, Any]:
        """
        对检索结果进行重排序

        Args:
            query: 查询文本
            documents: 文档列表

        Returns:
            重排序结果
        """
        try:
            # 确保模型已加载
            if not self.model_loaded:
                loaded = await self.load_model()
                if not loaded:
                    return {
                        "success": False,
                        "error": "模型加载失败",
                        "error_code": "MODEL_LOADING_FAILED"
                    }

            # 验证输入
            if not query or len(query.strip()) == 0:
                return {
                    "success": False,
                    "error": "查询不能为空",
                    "error_code": "EMPTY_QUERY"
                }

            if not documents or len(documents) == 0:
                return {
                    "success": False,
                    "error": "文档列表不能为空",
                    "error_code": "EMPTY_DOCUMENTS"
                }

            # 检查输入长度
            if len(query) > self.max_sequence_length:
                logger.warning("query_too_long", length=len(query), max_length=self.max_sequence_length)

            for i, doc in enumerate(documents):
                if len(doc) > self.max_sequence_length:
                    logger.warning("document_too_long", index=i, length=len(doc), max_length=self.max_sequence_length)

            # Identity reranker: preserve original order with normalized scores
            n = len(documents)
            reranked_results = [
                {
                    "document": doc,
                    "original_index": i,
                    "rerank_score": 1.0 - (i / max(n, 1)),
                    "rank": i + 1,
                }
                for i, doc in enumerate(documents)
            ]

            result = {
                "success": True,
                "reranked_results": reranked_results,
                "metadata": {
                    "model": "identity-reranker",
                    "query_length": len(query),
                    "document_count": n,
                }
            }

            logger.info(
                "bge_rerank_completed",
                document_count=len(documents),
                top_score=reranked_results[0]["rerank_score"] if reranked_results else 0
            )

            return result

        except Exception as e:
            logger.error("bge_rerank_failed", error=str(e), document_count=len(documents))
            return {
                "success": False,
                "error": f"重排序失败: {str(e)}",
                "error_code": "RERANK_EXCEPTION"
            }

    async def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息

        Returns:
            模型信息
        """
        return {
            "success": True,
            "model_info": {
                "name": "BGE-Rerank",
                "path": self.model_path,
                "device": self.device,
                "loaded": self.model_loaded,
                "max_sequence_length": self.max_sequence_length,
                "batch_size": self.batch_size,
                "use_gpu": self.use_gpu
            }
        }

    async def unload_model(self) -> bool:
        """
        卸载模型

        Returns:
            是否成功卸载
        """
        try:
            if self.model_loaded:
                # 释放模型资源
                self.model_instance = None
                self.model_loaded = False
                logger.info("bge_rerank_model_unloaded")
                return True
            return True
        except Exception as e:
            logger.error("bge_rerank_model_unload_failed", error=str(e))
            return False

    async def validate_model_availability(self) -> bool:
        """
        Identity reranker is always available.

        Returns:
            Always True
        """
        return True