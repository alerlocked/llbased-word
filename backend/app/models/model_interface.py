"""
工艺文件辅助编辑系统 - 模型接口定义
定义统一的模型服务接口
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncGenerator


class ModelInterface(ABC):
    """
    模型接口基类

    定义所有AI模型必须实现的统一接口
    """

    @abstractmethod
    async def load_model(self) -> bool:
        """
        加载模型

        Returns:
            是否成功加载
        """
        pass

    @abstractmethod
    async def unload_model(self) -> bool:
        """
        卸载模型

        Returns:
            是否成功卸载
        """
        pass

    @abstractmethod
    async def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息

        Returns:
            模型信息
        """
        pass

    @abstractmethod
    async def validate_model_availability(self) -> bool:
        """
        验证模型可用性

        Returns:
            模型是否可用
        """
        pass


class TextGenerationModel(ModelInterface):
    """
    文本生成模型接口
    """

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        生成文本

        Args:
            prompt: 输入提示
            max_tokens: 最大生成token数
            temperature: 温度参数
            top_p: Top-p采样参数
            stream: 是否流式输出

        Returns:
            生成结果
        """
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式生成文本

        Args:
            prompt: 输入提示
            max_tokens: 最大生成token数
            temperature: 温度参数
            top_p: Top-p采样参数

        Yields:
            生成的文本片段
        """
        pass


class EmbeddingModel(ModelInterface):
    """
    嵌入模型接口
    """

    @abstractmethod
    async def encode_texts(self, texts: List[str]) -> Dict[str, Any]:
        """
        对文本进行向量化

        Args:
            texts: 文本列表

        Returns:
            向量化结果
        """
        pass

    @abstractmethod
    async def encode_single_text(self, text: str) -> Dict[str, Any]:
        """
        对单个文本进行向量化

        Args:
            text: 文本

        Returns:
            向量化结果
        """
        pass


class RerankModel(ModelInterface):
    """
    重排序模型接口
    """

    @abstractmethod
    async def rerank_results(self, query: str, documents: List[str]) -> Dict[str, Any]:
        """
        对检索结果进行重排序

        Args:
            query: 查询文本
            documents: 文档列表

        Returns:
            重排序结果
        """
        pass