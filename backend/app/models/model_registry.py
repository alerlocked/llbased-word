"""
工艺文件辅助编辑系统 - 模型注册表
管理所有可用的AI模型
"""
from typing import Dict, Any, Optional, Type
import json
from pathlib import Path

from app.shared.logging import get_logger
from .model_interface import ModelInterface, TextGenerationModel, EmbeddingModel, RerankModel

logger = get_logger(__name__)


class ModelRegistry:
    """
    模型注册表

    负责管理所有可用的AI模型，
    提供模型的注册、查找和实例化功能
    """

    def __init__(self, config_file: str = "backend/app/models/model_config.json"):
        """
        初始化模型注册表

        Args:
            config_file: 模型配置文件路径
        """
        self.config_file = config_file
        self.model_configs = self._load_model_configs()
        self.registered_models: Dict[str, Type[ModelInterface]] = {}
        self.model_instances: Dict[str, ModelInterface] = {}

        logger.info("model_registry_initialized", config_file=config_file)

    def _load_model_configs(self) -> Dict[str, Any]:
        """
        加载模型配置

        Returns:
            模型配置字典
        """
        try:
            config_path = Path(self.config_file)
            if not config_path.exists():
                logger.warning("model_config_file_not_found", path=self.config_file)
                return {}

            with open(config_path, 'r', encoding='utf-8') as f:
                configs = json.load(f)

            logger.info("model_configs_loaded", model_count=len(configs))
            return configs

        except Exception as e:
            logger.error("model_config_loading_failed", error=str(e), path=self.config_file)
            return {}

    def register_model(self, model_name: str, model_class: Type[ModelInterface]):
        """
        注册模型

        Args:
            model_name: 模型名称
            model_class: 模型类
        """
        self.registered_models[model_name] = model_class
        logger.info("model_registered", model_name=model_name)

    def get_model_class(self, model_name: str) -> Optional[Type[ModelInterface]]:
        """
        获取模型类

        Args:
            model_name: 模型名称

        Returns:
            模型类，如果不存在则返回None
        """
        return self.registered_models.get(model_name)

    def get_model_config(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        获取模型配置

        Args:
            model_name: 模型名称

        Returns:
            模型配置，如果不存在则返回None
        """
        return self.model_configs.get(model_name)

    def create_model_instance(self, model_name: str, **kwargs) -> Optional[ModelInterface]:
        """
        创建模型实例

        Args:
            model_name: 模型名称
            **kwargs: 模型初始化参数

        Returns:
            模型实例，如果创建失败则返回None
        """
        try:
            # 获取模型类
            model_class = self.get_model_class(model_name)
            if not model_class:
                logger.error("model_class_not_found", model_name=model_name)
                return None

            # 获取模型配置
            model_config = self.get_model_config(model_name)
            if not model_config:
                logger.warning("model_config_not_found", model_name=model_name)

            # 合并配置和参数
            final_config = {}
            if model_config:
                final_config.update(model_config)
            if kwargs:
                final_config.update(kwargs)

            # 创建模型实例
            model_instance = model_class(final_config)
            self.model_instances[model_name] = model_instance

            logger.info("model_instance_created", model_name=model_name)
            return model_instance

        except Exception as e:
            logger.error("model_instance_creation_failed", error=str(e), model_name=model_name)
            return None

    def get_model_instance(self, model_name: str) -> Optional[ModelInterface]:
        """
        获取模型实例

        Args:
            model_name: 模型名称

        Returns:
            模型实例，如果不存在则返回None
        """
        return self.model_instances.get(model_name)

    def list_available_models(self) -> Dict[str, Dict[str, Any]]:
        """
        列出所有可用模型

        Returns:
            可用模型信息字典
        """
        available_models = {}

        for model_name in self.registered_models.keys():
            model_config = self.get_model_config(model_name)
            available_models[model_name] = {
                "registered": True,
                "config": model_config or {},
                "instantiated": model_name in self.model_instances
            }

        return available_models

    def validate_model_availability(self, model_name: str) -> bool:
        """
        验证模型可用性

        Args:
            model_name: 模型名称

        Returns:
            模型是否可用
        """
        try:
            model_instance = self.get_model_instance(model_name)
            if model_instance:
                return model_instance.validate_model_availability()

            # 如果没有实例，尝试创建一个临时实例
            temp_instance = self.create_model_instance(model_name)
            if temp_instance:
                availability = temp_instance.validate_model_availability()
                # 清理临时实例
                del temp_instance
                return availability

            return False

        except Exception as e:
            logger.error("model_availability_validation_failed", error=str(e), model_name=model_name)
            return False

    def get_text_generation_models(self) -> Dict[str, Type[TextGenerationModel]]:
        """
        获取所有文本生成模型

        Returns:
            文本生成模型字典
        """
        text_models = {}
        for name, model_class in self.registered_models.items():
            if issubclass(model_class, TextGenerationModel):
                text_models[name] = model_class
        return text_models

    def get_embedding_models(self) -> Dict[str, Type[EmbeddingModel]]:
        """
        获取所有嵌入模型

        Returns:
            嵌入模型字典
        """
        embedding_models = {}
        for name, model_class in self.registered_models.items():
            if issubclass(model_class, EmbeddingModel):
                embedding_models[name] = model_class
        return embedding_models

    def get_rerank_models(self) -> Dict[str, Type[RerankModel]]:
        """
        获取所有重排序模型

        Returns:
            重排序模型字典
        """
        rerank_models = {}
        for name, model_class in self.registered_models.items():
            if issubclass(model_class, RerankModel):
                rerank_models[name] = model_class
        return rerank_models