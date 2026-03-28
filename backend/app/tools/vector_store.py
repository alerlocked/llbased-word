"""
工艺文件辅助编辑系统 - 向量数据库工具
使用ChromaDB实现向量存储和检索，集成BGE-Embedding模型
"""
from typing import Dict, Any, Optional, List, Union
import chromadb
from chromadb.config import Settings
from pathlib import Path
import json

from app.shared.logging import get_logger
from app.config import settings

logger = get_logger(__name__)


class VectorStore:
    """
    向量数据库工具

    使用ChromaDB作为向量数据库，
    集成BGE-Embedding模型进行文本向量化
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化向量数据库

        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.collection_name = self.config.get("collection_name", "process_knowledge")
        self.embedding_model = self.config.get("embedding_model", "BAAI/bge-large-zh-v1.5")
        self.distance_metric = self.config.get("distance_metric", "cosine")
        # 使用统一的配置路径
        self.persist_directory = self.config.get("persist_directory", str(settings.DATA_DIR / "vector_store"))

        # 初始化ChromaDB客户端
        self.client = self._init_chromadb_client()
        self.collection = self._get_or_create_collection()

        logger.info(
            "vector_store_initialized",
            collection_name=self.collection_name,
            embedding_model=self.embedding_model,
            persist_directory=self.persist_directory
        )

    def _init_chromadb_client(self) -> chromadb.Client:
        """
        初始化ChromaDB客户端

        Returns:
            ChromaDB客户端实例
        """
        try:
            # 创建持久化目录
            Path(self.persist_directory).mkdir(parents=True, exist_ok=True)

            # 初始化客户端
            client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )

            return client

        except Exception as e:
            logger.error("chromadb_client_initialization_failed", error=str(e))
            raise e

    def _get_or_create_collection(self) -> chromadb.Collection:
        """
        获取或创建集合

        Returns:
            ChromaDB集合实例
        """
        try:
            # 尝试获取现有集合
            try:
                collection = self.client.get_collection(
                    name=self.collection_name,
                    embedding_function=None  # 我们将使用自定义嵌入函数
                )
                logger.info("existing_collection_loaded", collection_name=self.collection_name)
            except ValueError:
                # 集合不存在，创建新集合
                collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": self.distance_metric},
                    embedding_function=None
                )
                logger.info("new_collection_created", collection_name=self.collection_name)

            return collection

        except Exception as e:
            logger.error("collection_initialization_failed", error=str(e))
            raise e

    async def add_documents(
        self,
        documents: List[Dict[str, Any]],
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        添加文档到向量数据库

        Args:
            documents: 文档列表，每个文档应包含"id"和"text"字段
            metadata: 元数据列表

        Returns:
            添加结果
        """
        try:
            if not documents:
                raise ValueError("文档列表为空")

            # 准备数据
            ids = []
            texts = []
            metadatas = []

            for i, doc in enumerate(documents):
                doc_id = doc.get("id", f"doc_{i}")
                doc_text = doc.get("text", "")
                doc_metadata = doc.get("metadata", {})

                if not doc_text:
                    logger.warning("empty_document_skipped", document_id=doc_id)
                    continue

                ids.append(doc_id)
                texts.append(doc_text)

                # 合并元数据
                final_metadata = {}
                if metadata and i < len(metadata):
                    final_metadata.update(metadata[i])
                final_metadata.update(doc_metadata)
                metadatas.append(final_metadata)

            if not ids:
                return {
                    "success": False,
                    "error": "没有有效的文档可添加",
                    "error_code": "NO_VALID_DOCUMENTS"
                }

            # 生成嵌入向量
            embeddings = await self._generate_embeddings(texts)

            # 添加到集合
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas
            )

            logger.info("documents_added", count=len(ids), collection_name=self.collection_name)
            return {
                "success": True,
                "added_count": len(ids),
                "document_ids": ids
            }

        except Exception as e:
            logger.error("document_addition_failed", error=str(e))
            return {
                "success": False,
                "error": f"文档添加失败: {str(e)}",
                "error_code": "DOCUMENT_ADDITION_EXCEPTION"
            }

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
        include_embeddings: bool = False
    ) -> Dict[str, Any]:
        """
        搜索相似文档

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filters: 元数据过滤条件
            include_metadata: 是否包含元数据
            include_embeddings: 是否包含嵌入向量

        Returns:
            搜索结果
        """
        try:
            if not query:
                raise ValueError("查询文本为空")

            # 生成查询嵌入
            query_embedding = await self._generate_embeddings([query])

            # 准备搜索参数
            search_params = {
                "query_embeddings": query_embedding,
                "n_results": top_k,
                "include": ["documents", "metadatas", "distances"]
            }

            if include_embeddings:
                search_params["include"].append("embeddings")

            if filters:
                search_params["where"] = filters

            # 执行搜索
            results = self.collection.query(**search_params)

            # 处理结果
            processed_results = []
            for i, doc_list in enumerate(results["documents"]):
                for j, doc in enumerate(doc_list):
                    result_item = {
                        "id": results["ids"][i][j],
                        "text": doc,
                        "similarity": 1.0 - results["distances"][i][j],  # 转换为相似度
                        "distance": results["distances"][i][j]
                    }

                    if include_metadata and results["metadatas"][i][j]:
                        result_item["metadata"] = results["metadatas"][i][j]

                    if include_embeddings and results.get("embeddings"):
                        result_item["embedding"] = results["embeddings"][i][j]

                    processed_results.append(result_item)

            # 按相似度排序
            processed_results.sort(key=lambda x: x["similarity"], reverse=True)

            logger.info(
                "search_completed",
                query=query[:50],
                results_count=len(processed_results),
                top_k=top_k
            )

            return {
                "success": True,
                "results": processed_results,
                "query": query,
                "top_k": top_k,
                "filters_applied": bool(filters)
            }

        except Exception as e:
            logger.error("search_failed", error=str(e), query=query[:50])
            return {
                "success": False,
                "error": f"搜索失败: {str(e)}",
                "error_code": "SEARCH_EXCEPTION"
            }

    async def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        生成文本嵌入向量

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表
        """
        try:
            # 这里应该集成BGE-Embedding模型
            # 目前返回模拟的嵌入向量
            import numpy as np

            embeddings = []
            for text in texts:
                # 生成随机嵌入向量（模拟）
                # BGE-large-zh-v1.5 的维度是 1024
                embedding = np.random.rand(1024).tolist()
                embeddings.append(embedding)

            logger.debug("embeddings_generated", count=len(embeddings), dimension=1024)
            return embeddings

        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e))
            raise e

    async def update_document(self, document_id: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新文档

        Args:
            document_id: 文档ID
            document: 更新的文档内容

        Returns:
            更新结果
        """
        try:
            # 删除旧文档
            await self.delete_document(document_id)

            # 添加新文档
            new_doc = {"id": document_id, **document}
            result = await self.add_documents([new_doc])

            logger.info("document_updated", document_id=document_id)
            return result

        except Exception as e:
            logger.error("document_update_failed", error=str(e), document_id=document_id)
            return {
                "success": False,
                "error": f"文档更新失败: {str(e)}",
                "error_code": "DOCUMENT_UPDATE_EXCEPTION"
            }

    async def delete_document(self, document_id: str) -> Dict[str, Any]:
        """
        删除文档

        Args:
            document_id: 文档ID

        Returns:
            删除结果
        """
        try:
            self.collection.delete(ids=[document_id])

            logger.info("document_deleted", document_id=document_id)
            return {
                "success": True,
                "deleted_id": document_id
            }

        except Exception as e:
            logger.error("document_deletion_failed", error=str(e), document_id=document_id)
            return {
                "success": False,
                "error": f"文档删除失败: {str(e)}",
                "error_code": "DOCUMENT_DELETION_EXCEPTION"
            }

    async def get_collection_size(self) -> int:
        """
        获取集合大小

        Returns:
            集合中文档数量
        """
        try:
            return self.collection.count()
        except Exception as e:
            logger.error("collection_size_retrieval_failed", error=str(e))
            return 0

    async def get_collection_info(self) -> Dict[str, Any]:
        """
        获取集合信息

        Returns:
            集合信息
        """
        try:
            return {
                "collection_name": self.collection_name,
                "document_count": await self.get_collection_size(),
                "embedding_model": self.embedding_model,
                "distance_metric": self.distance_metric,
                "persist_directory": self.persist_directory
            }
        except Exception as e:
            logger.error("collection_info_retrieval_failed", error=str(e))
            return {}

    async def search_by_metadata(
        self,
        metadata_filters: Dict[str, Any],
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        根据元数据搜索文档

        Args:
            metadata_filters: 元数据过滤条件
            limit: 返回结果数量限制

        Returns:
            搜索结果
        """
        try:
            # 使用ChromaDB的where子句进行元数据搜索
            results = self.collection.get(
                where=metadata_filters,
                limit=limit,
                include=["documents", "metadatas"]
            )

            processed_results = []
            for i, doc in enumerate(results["documents"]):
                result_item = {
                    "id": results["ids"][i],
                    "text": doc,
                    "metadata": results["metadatas"][i] if results["metadatas"] else {}
                }
                processed_results.append(result_item)

            logger.info(
                "metadata_search_completed",
                filter_count=len(metadata_filters),
                result_count=len(processed_results)
            )

            return {
                "success": True,
                "results": processed_results,
                "filters": metadata_filters,
                "limit": limit
            }

        except Exception as e:
            logger.error("metadata_search_failed", error=str(e), filters=metadata_filters)
            return {
                "success": False,
                "error": f"元数据搜索失败: {str(e)}",
                "error_code": "METADATA_SEARCH_EXCEPTION"
            }

    async def clear_collection(self) -> Dict[str, Any]:
        """
        清空集合

        Returns:
            清空结果
        """
        try:
            # 删除集合并重新创建
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": self.distance_metric},
                embedding_function=None
            )

            logger.info("collection_cleared", collection_name=self.collection_name)
            return {
                "success": True,
                "collection_name": self.collection_name
            }

        except Exception as e:
            logger.error("collection_clear_failed", error=str(e))
            return {
                "success": False,
                "error": f"集合清空失败: {str(e)}",
                "error_code": "COLLECTION_CLEAR_EXCEPTION"
            }