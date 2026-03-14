"""
工艺文件辅助编辑系统 - 模型服务
提供统一的模型服务接口，支持不同模型的切换
"""
from typing import Dict, Any, Optional, List, AsyncGenerator
import asyncio

from app.shared.logging import get_logger
from .model_registry import ModelRegistry
from .deepseek_r1 import DeepSeekR1Model
from .bge_embedding import BGEEmbeddingModel
from .bge_rerank import BGERerankModel

logger = get_logger(__name__)


class ModelService:
    """
    模型服务

    提供统一的模型服务接口，
    支持DeepSeek-R1、BGE-Embedding、BGE-Rerank等模型的切换和管理
    """

    def __init__(self):
        """初始化模型服务"""
        # 初始化模型注册表
        self.model_registry = ModelRegistry()

        # 注册所有可用模型
        self._register_models()

        logger.info("model_service_initialized")

    def _register_models(self):
        """注册所有模型"""
        self.model_registry.register_model("deepseek_r1", DeepSeekR1Model)
        self.model_registry.register_model("bge_embedding", BGEEmbeddingModel)
        self.model_registry.register_model("bge_rerank", BGERerankModel)

        logger.info("models_registered", count=3)

    async def get_text_generation_model(self, model_name: str = "deepseek_r1", **kwargs) -> Optional[DeepSeekR1Model]:
        """
        获取文本生成模型

        Args:
            model_name: 模型名称
            **kwargs: 模型参数

        Returns:
            文本生成模型实例
        """
        try:
            model_instance = self.model_registry.get_model_instance(model_name)
            if not model_instance:
                model_instance = self.model_registry.create_model_instance(model_name, **kwargs)
                if not model_instance:
                    return None

            return model_instance

        except Exception as e:
            logger.error("text_generation_model_retrieval_failed", error=str(e), model_name=model_name)
            return None

    async def get_embedding_model(self, model_name: str = "bge_embedding", **kwargs) -> Optional[BGEEmbeddingModel]:
        """
        获取嵌入模型

        Args:
            model_name: 模型名称
            **kwargs: 模型参数

        Returns:
            嵌入模型实例
        """
        try:
            model_instance = self.model_registry.get_model_instance(model_name)
            if not model_instance:
                model_instance = self.model_registry.create_model_instance(model_name, **kwargs)
                if not model_instance:
                    return None

            return model_instance

        except Exception as e:
            logger.error("embedding_model_retrieval_failed", error=str(e), model_name=model_name)
            return None

    async def get_rerank_model(self, model_name: str = "bge_rerank", **kwargs) -> Optional[BGERerankModel]:
        """
        获取重排序模型

        Args:
            model_name: 模型名称
            **kwargs: 模型参数

        Returns:
            重排序模型实例
        """
        try:
            model_instance = self.model_registry.get_model_instance(model_name)
            if not model_instance:
                model_instance = self.model_registry.create_model_instance(model_name, **kwargs)
                if not model_instance:
                    return None

            return model_instance

        except Exception as e:
            logger.error("rerank_model_retrieval_failed", error=str(e), model_name=model_name)
            return None

    async def generate_text(
        self,
        prompt: str,
        model_name: str = "deepseek_r1",
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成文本

        Args:
            prompt: 输入提示
            model_name: 模型名称
            **kwargs: 生成参数

        Returns:
            生成结果
        """
        try:
            model = await self.get_text_generation_model(model_name, **kwargs)
            if not model:
                return {
                    "success": False,
                    "error": f"无法获取模型: {model_name}",
                    "error_code": "MODEL_NOT_AVAILABLE"
                }

            result = await model.generate_text(prompt, **kwargs)
            return result

        except Exception as e:
            logger.error("text_generation_failed", error=str(e), model_name=model_name)
            return {
                "success": False,
                "error": f"文本生成失败: {str(e)}",
                "error_code": "GENERATION_EXCEPTION"
            }

    async def encode_texts(
        self,
        texts: List[str],
        model_name: str = "bge_embedding",
        **kwargs
    ) -> Dict[str, Any]:
        """
        对文本进行向量化

        Args:
            texts: 文本列表
            model_name: 模型名称
            **kwargs: 编码参数

        Returns:
            向量化结果
        """
        try:
            model = await self.get_embedding_model(model_name, **kwargs)
            if not model:
                return {
                    "success": False,
                    "error": f"无法获取模型: {model_name}",
                    "error_code": "MODEL_NOT_AVAILABLE"
                }

            result = await model.encode_texts(texts, **kwargs)
            return result

        except Exception as e:
            logger.error("text_encoding_failed", error=str(e), model_name=model_name)
            return {
                "success": False,
                "error": f"文本向量化失败: {str(e)}",
                "error_code": "ENCODING_EXCEPTION"
            }

    async def rerank_results(
        self,
        query: str,
        documents: List[str],
        model_name: str = "bge_rerank",
        **kwargs
    ) -> Dict[str, Any]:
        """
        对检索结果进行重排序

        Args:
            query: 查询文本
            documents: 文档列表
            model_name: 模型名称
            **kwargs: 重排序参数

        Returns:
            重排序结果
        """
        try:
            model = await self.get_rerank_model(model_name, **kwargs)
            if not model:
                return {
                    "success": False,
                    "error": f"无法获取模型: {model_name}",
                    "error_code": "MODEL_NOT_AVAILABLE"
                }

            result = await model.rerank_results(query, documents, **kwargs)
            return result

        except Exception as e:
            logger.error("result_reranking_failed", error=str(e), model_name=model_name)
            return {
                "success": False,
                "error": f"结果重排序失败: {str(e)}",
                "error_code": "RERANK_EXCEPTION"
            }

    async def get_available_models(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有可用模型

        Returns:
            可用模型信息
        """
        return self.model_registry.list_available_models()

    async def validate_all_models(self) -> Dict[str, bool]:
        """
        验证所有模型的可用性

        Returns:
            模型可用性字典
        """
        available_models = self.model_registry.list_available_models()
        validation_results = {}

        for model_name in available_models.keys():
            validation_results[model_name] = self.model_registry.validate_model_availability(model_name)

        return validation_results

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康检查结果
        """
        try:
            # 检查模型注册表
            models = await self.get_available_models()
            model_count = len(models)

            # 验证模型可用性
            validation_results = await self.validate_all_models()
            available_models = sum(1 for available in validation_results.values() if available)

            health_status = {
                "status": "healthy" if available_models > 0 else "degraded",
                "models_registered": model_count,
                "models_available": available_models,
                "model_validation_results": validation_results,
                "timestamp": "timestamp_placeholder"
            }

            logger.info("model_service_health_check", status=health_status["status"])
            return health_status

        except Exception as e:
            logger.error("health_check_failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": "timestamp_placeholder"
            }