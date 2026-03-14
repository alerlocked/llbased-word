"""
RAGRetrieverTool - RAG向量检索工具
从向量知识库检索相关背景知识
"""
import json
from typing import List, Dict
from pathlib import Path

from app.utils.logger import logger


class RAGRetrieverTool:
    """
    RAG检索工具 - 向量知识库检索
    使用ChromaDB存储和检索文档向量
    """
    
    def __init__(self, config):
        """
        初始化RAG检索工具
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.vectorstore = None
        self.embeddings = None
        self.text_splitter = None
    
    def _init_components(self):
        """延迟初始化组件"""
        if self.vectorstore is not None:
            return
        
        try:
            from langchain_community.vectorstores import Chroma
            from langchain_openai import OpenAIEmbeddings
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            
            # 使用硅基流动的OpenAI兼容API初始化Embedding模型
            logger.info("🔧 初始化Embedding模型(硅基流动API)...")
            self.embeddings = OpenAIEmbeddings(
                model=self.config.SILICONFLOW_EMBEDDING_MODEL,
                openai_api_key=self.config.SILICONFLOW_API_KEY,
                openai_api_base=self.config.SILICONFLOW_BASE_URL
            )
            
            logger.info(f"✅ 使用硅基流动API: {self.config.SILICONFLOW_EMBEDDING_MODEL}")
            
            # 初始化文本分割器
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50
            )
            
            # 初始化向量数据库
            chroma_dir = Path(self.config.DATA_DIR) / "chroma_db"
            chroma_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"🔧 初始化向量数据库: {chroma_dir}")
            self.vectorstore = Chroma(
                persist_directory=str(chroma_dir),
                embedding_function=self.embeddings,
                collection_name="journalist_knowledge"
            )
            
            logger.info("✅ RAG组件初始化成功")
            
        except ImportError as e:
            logger.warning(f"⚠️ RAG依赖未安装: {str(e)}")
            self.vectorstore = None
        except Exception as e:
            logger.error(f"❌ RAG组件初始化失败: {str(e)}")
            self.vectorstore = None
    
    def retrieve(self, query: str, k: int = 5, project_id: int = None) -> str:
        """
        检索相关文档
        
        Args:
            query: 语义查询
            k: 返回结果数量
            project_id: 项目ID（用于过滤，防止素材污染）
        
        Returns:
            检索结果（JSON格式字符串）
        """
        logger.info(f"📚 开始知识库检索: {query} (项目过滤: {project_id})")
        
        try:
            # 初始化组件
            self._init_components()
            
            if self.vectorstore is None:
                logger.warning("⚠️ 向量数据库不可用，返回空结果")
                return json.dumps({
                    "status": "unavailable",
                    "error": "向量数据库不可用",
                    "results": []
                }, ensure_ascii=False, indent=2)
            
            # 执行检索
            try:
                # 构造过滤条件
                search_kwargs = {"k": k}
                if project_id:
                    # ChromaDB 的过滤语法
                    search_kwargs["filter"] = {"project_id": project_id}
                
                docs = self.vectorstore.similarity_search(query, **search_kwargs)
                
                # 格式化结果
                results = []
                for doc in docs:
                    results.append({
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "source": doc.metadata.get("source", "unknown")
                    })
                
                logger.info(f"✅ 知识库检索完成，找到{len(results)}条结果")
                
                result_json = {
                    "status": "success",
                    "query": query,
                    "total_results": len(results),
                    "results": results
                }
                
                return json.dumps(result_json, ensure_ascii=False, indent=2)
                
            except Exception as e:
                logger.error(f"❌ 检索执行失败: {str(e)}")
                return json.dumps({
                    "status": "error",
                    "error": f"检索执行失败: {str(e)}",
                    "results": []
                }, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"❌ 知识库检索失败: {str(e)}")
            error_result = {
                "status": "error",
                "error": str(e),
                "results": []
            }
            return json.dumps(error_result, ensure_ascii=False, indent=2)
    
    def add_documents(self, documents: List[str], metadatas: List[Dict]):
        """
        添加文档到知识库
        
        Args:
            documents: 文档列表
            metadatas: 元数据列表
        """
        logger.info(f"📥 添加{len(documents)}个文档到知识库...")
        
        try:
            self._init_components()
            
            if self.vectorstore is None:
                logger.warning("⚠️ 向量数据库不可用")
                return
            
            # 分割文档
            chunks = self.text_splitter.create_documents(
                documents, 
                metadatas=metadatas
            )
            
            # 添加到向量库
            self.vectorstore.add_documents(chunks)
            
            logger.info(f"✅ 成功添加{len(chunks)}个文档块")
            
        except Exception as e:
            logger.error(f"❌ 添加文档失败: {str(e)}")

