"""
RAG同步服务
将转写、文章、编辑器内容、上传文档同步到ChromaDB向量库
"""
from typing import List, Dict, Optional
from pathlib import Path
from sqlalchemy.orm import Session
import json

from app.utils.logger import logger
from app.config import settings


class RAGSyncService:
    """
    RAG同步服务
    负责将各类文档同步到ChromaDB向量数据库
    """
    
    def __init__(self):
        """初始化RAG同步服务"""
        self.vectorstore = None
        self.embeddings = None
        self.text_splitter = None
        self._initialized = False
    
    def _init_components(self):
        """延迟初始化组件"""
        if self._initialized:
            return
        
        try:
            from langchain_community.vectorstores import Chroma
            from langchain_openai import OpenAIEmbeddings
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            
            logger.info("🔧 初始化RAG同步服务组件...")
            
            # 使用硅基流动的OpenAI兼容API初始化Embedding模型
            self.embeddings = OpenAIEmbeddings(
                model=settings.SILICONFLOW_EMBEDDING_MODEL,
                openai_api_key=settings.SILICONFLOW_API_KEY,
                openai_api_base=settings.SILICONFLOW_BASE_URL
            )
            
            logger.info(f"✅ 使用硅基流动API: {settings.SILICONFLOW_EMBEDDING_MODEL}")
            
            # 初始化文本分割器
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                length_function=len
            )
            
            # 初始化向量数据库
            chroma_dir = Path(settings.DATA_DIR) / "chroma_db"
            chroma_dir.mkdir(parents=True, exist_ok=True)
            
            self.vectorstore = Chroma(
                persist_directory=str(chroma_dir),
                embedding_function=self.embeddings,
                collection_name="journalist_knowledge"
            )
            
            self._initialized = True
            logger.info("✅ RAG同步服务组件初始化成功")
            
        except Exception as e:
            logger.error(f"❌ RAG同步服务初始化失败: {str(e)}")
            self._initialized = False

    async def sync_article(self, article_id: int, title: str, content: str, metadata: Dict):
        """
        同步文章到RAG
        
        Args:
            article_id: 文章ID
            title: 文章标题
            content: 文章内容
            metadata: 元数据
        """
        logger.info(f"📄 同步文章到RAG: article_id={article_id}")
        
        try:
            self._init_components()
            
            if not self._initialized:
                logger.warning("⚠️ RAG服务未初始化，跳过同步")
                return
            
            # 文档唯一ID
            doc_id = f"article_{article_id}"
            
            # 先删除旧文档
            await self._delete_document(doc_id)
            
            # 组合标题和内容
            full_content = f"{title}\n\n{content}"
            
            # 分割文本
            chunks = self.text_splitter.split_text(full_content)
            
            # 准备元数据
            metadatas = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = {
                    **metadata,
                    "doc_id": doc_id,
                    "doc_type": "article",
                    "article_id": article_id,
                    "title": title,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
                metadatas.append(chunk_metadata)
            
            # 添加到向量库
            self.vectorstore.add_texts(
                texts=chunks,
                metadatas=metadatas
            )
            
            logger.info(f"✅ 文章已同步: {len(chunks)}个文本块")
            
        except Exception as e:
            logger.error(f"❌ 同步文章失败: {str(e)}")
    
    async def sync_project_content(self, project_id: int, content: str, metadata: Dict):
        """
        同步项目编辑器内容到RAG（覆盖更新）
        
        Args:
            project_id: 项目ID
            content: 编辑器内容
            metadata: 元数据
        """
        logger.info(f"📋 同步项目内容到RAG: project_id={project_id}")
        
        try:
            self._init_components()
            
            if not self._initialized:
                logger.warning("⚠️ RAG服务未初始化，跳过同步")
                return
            
            # 文档唯一ID（按项目ID覆盖）
            doc_id = f"project_{project_id}"
            
            # 先删除旧文档
            await self._delete_document(doc_id)
            
            # 如果内容为空，只删除不添加
            if not content or content.strip() == "":
                logger.info(f"ℹ️ 项目内容为空，仅删除旧文档")
                return
            
            # 分割文本
            chunks = self.text_splitter.split_text(content)
            
            # 准备元数据
            metadatas = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = {
                    **metadata,
                    "doc_id": doc_id,
                    "doc_type": "project",
                    "project_id": project_id,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
                metadatas.append(chunk_metadata)
            
            # 添加到向量库
            self.vectorstore.add_texts(
                texts=chunks,
                metadatas=metadatas
            )
            
            logger.info(f"✅ 项目内容已同步（覆盖更新）: {len(chunks)}个文本块")
            
        except Exception as e:
            logger.error(f"❌ 同步项目内容失败: {str(e)}")
    
    async def sync_uploaded_document(
        self, 
        doc_id: str, 
        filename: str, 
        content: str, 
        metadata: Dict
    ):
        """
        同步上传的参考文档到RAG
        
        Args:
            doc_id: 文档唯一ID
            filename: 文件名
            content: 文档内容
            metadata: 元数据
        """
        logger.info(f"📤 同步上传文档到RAG: {filename}")
        
        try:
            self._init_components()
            
            if not self._initialized:
                logger.warning("⚠️ RAG服务未初始化，跳过同步")
                return
            
            # 先删除旧文档
            await self._delete_document(doc_id)
            
            # 分割文本
            chunks = self.text_splitter.split_text(content)
            
            # 准备元数据
            metadatas = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = {
                    **metadata,
                    "doc_id": doc_id,
                    "doc_type": "uploaded_document",
                    "filename": filename,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
                metadatas.append(chunk_metadata)
            
            # 添加到向量库
            self.vectorstore.add_texts(
                texts=chunks,
                metadatas=metadatas
            )
            
            logger.info(f"✅ 上传文档已同步: {len(chunks)}个文本块")
            
        except Exception as e:
            logger.error(f"❌ 同步上传文档失败: {str(e)}")
    
    async def sync_figure_captions(
        self,
        material_id: int,
        figures: List[Dict],
        metadata: Dict
    ):
        """
        同步图片描述到RAG（用于图片检索）
        
        Args:
            material_id: 素材ID
            figures: 图片列表，每个包含 caption 和 file_path
            metadata: 元数据
        """
        logger.info(f"🖼️ 同步图片描述到RAG: material_id={material_id}, 共{len(figures)}张图片")
        
        try:
            self._init_components()
            
            if not self._initialized:
                logger.warning("⚠️ RAG服务未初始化，跳过同步")
                return
            
            # 文档唯一ID
            doc_id = f"material_{material_id}_figures"
            
            # 先删除旧文档
            await self._delete_document(doc_id)
            
            # 为每张图片的描述创建文本块
            texts = []
            metadatas = []
            
            for idx, figure in enumerate(figures):
                caption = figure.get("caption", "")
                if caption:
                    # 组合图片路径和描述，便于检索
                    text = f"图片: {figure.get('file_path', '')}\n描述: {caption}"
                    texts.append(text)
                    
                    chunk_metadata = {
                        **metadata,
                        "doc_id": doc_id,
                        "doc_type": "figure",
                        "material_id": material_id,
                        "figure_id": figure.get("id"),
                        "file_path": figure.get("file_path", ""),
                        "page_number": figure.get("page_number"),
                        "chunk_index": idx,
                        "total_chunks": len(figures)
                    }
                    metadatas.append(chunk_metadata)
            
            if texts:
                # 添加到向量库
                self.vectorstore.add_texts(
                    texts=texts,
                    metadatas=metadatas
                )
                
                logger.info(f"✅ 图片描述已同步: {len(texts)}个图片描述")
            
        except Exception as e:
            logger.error(f"❌ 同步图片描述失败: {str(e)}")
    
    async def _delete_document(self, doc_id: str):
        """
        删除指定ID的文档
        
        Args:
            doc_id: 文档唯一ID
        """
        try:
            if not self._initialized:
                return
            
            # 查询该doc_id的所有文档
            results = self.vectorstore.get(
                where={"doc_id": doc_id}
            )
            
            if results and results.get('ids'):
                # 删除所有匹配的文档
                self.vectorstore.delete(ids=results['ids'])
                logger.info(f"🗑️ 已删除旧文档: doc_id={doc_id}, 数量={len(results['ids'])}")
            
        except Exception as e:
            logger.warning(f"⚠️ 删除旧文档时出错: {str(e)}")
    
    async def delete_document_by_id(self, doc_id: str):
        """
        公开方法：删除指定ID的文档
        
        Args:
            doc_id: 文档唯一ID
        """
        logger.info(f"🗑️ 删除RAG文档: doc_id={doc_id}")
        
        try:
            self._init_components()
            
            if not self._initialized:
                logger.warning("⚠️ RAG服务未初始化，跳过删除")
                return
            
            await self._delete_document(doc_id)
            logger.info(f"✅ 文档已删除: doc_id={doc_id}")

        except Exception as e:
            logger.error(f"❌ 删除文档失败: {str(e)}")

    async def sync_all_articles(self, db: Session):
        """
        同步所有文章

        Args:
            db: 数据库会话
        """
        logger.info("🔄 开始同步所有文章...")

        try:
            from app.models.database import Article

            articles = db.query(Article).all()

            logger.info(f"📚 找到{len(articles)}篇文章")

            for article in articles:
                metadata = {
                    "article_type": article.article_type,
                    "status": article.status,
                    "created_at": str(article.created_at)
                }

                await self.sync_article(
                    article.id,
                    article.title,
                    article.content,
                    metadata
                )

            logger.info(f"✅ 所有文章同步完成")

        except Exception as e:
            logger.error(f"❌ 同步所有文章失败: {str(e)}")
    
    async def sync_all_projects(self, db: Session):
        """
        同步所有项目内容
        
        Args:
            db: 数据库会话
        """
        logger.info("🔄 开始同步所有项目内容...")
        
        try:
            from app.models.database import CreationProject
            
            projects = db.query(CreationProject).all()
            
            logger.info(f"📚 找到{len(projects)}个项目")
            
            for project in projects:
                if project.content:
                    metadata = {
                        "project_name": project.name,
                        "created_at": str(project.created_at),
                        "updated_at": str(project.updated_at)
                    }
                    
                    await self.sync_project_content(
                        project.id,
                        project.content,
                        metadata
                    )
            
            logger.info(f"✅ 所有项目内容同步完成")
            
        except Exception as e:
            logger.error(f"❌ 同步所有项目内容失败: {str(e)}")
    
    def parse_document_file(self, file_content: bytes, filename: str) -> str:
        """
        解析文档文件内容
        
        Args:
            file_content: 文件字节内容
            filename: 文件名
        
        Returns:
            解析后的文本内容
        """
        try:
            if filename.endswith('.txt'):
                # TXT文件直接解码
                return file_content.decode('utf-8')
            
            elif filename.endswith('.pdf'):
                # PDF文件解析
                try:
                    from PyPDF2 import PdfReader
                    from io import BytesIO
                    pdf = PdfReader(BytesIO(file_content))
                    text = '\n'.join([page.extract_text() for page in pdf.pages])
                    return text
                except ImportError:
                    logger.error("❌ PyPDF2未安装，无法解析PDF")
                    raise Exception("PDF解析需要安装PyPDF2")
            
            elif filename.endswith('.docx'):
                # Word文档解析
                try:
                    from docx import Document
                    from io import BytesIO
                    doc = Document(BytesIO(file_content))
                    text = '\n'.join([para.text for para in doc.paragraphs])
                    return text
                except ImportError:
                    logger.error("❌ python-docx未安装，无法解析Word文档")
                    raise Exception("Word文档解析需要安装python-docx")
            
            else:
                raise Exception(f"不支持的文件格式: {filename}")
        
        except Exception as e:
            logger.error(f"❌ 解析文档失败: {str(e)}")
            raise
    
    def get_statistics(self) -> Dict:
        """
        获取RAG知识库统计信息
        
        Returns:
            统计信息字典
        """
        try:
            self._init_components()
            
            if not self._initialized:
                return {
                    "status": "未初始化",
                    "total_documents": 0,
                    "total_chunks": 0
                }
            
            # 获取所有文档
            all_docs = self.vectorstore.get()
            
            # 统计不同类型的文档
            doc_types = {}
            unique_docs = set()
            
            if all_docs and all_docs.get('metadatas'):
                for metadata in all_docs['metadatas']:
                    doc_type = metadata.get('doc_type', 'unknown')
                    doc_id = metadata.get('doc_id', '')
                    
                    doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
                    unique_docs.add(doc_id)
            
            return {
                "status": "正常",
                "total_documents": len(unique_docs),
                "total_chunks": len(all_docs.get('ids', [])) if all_docs else 0,
                "doc_type_breakdown": doc_types
            }
            
        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {str(e)}")
            return {
                "status": "错误",
                "error": str(e)
            }
    
    # ==================== 多模态图片检索 ====================
    
    async def sync_image_embedding(
        self,
        image_id: str,
        image_path: str,
        caption: str,
        metadata: Dict
    ):
        """
        同步图片向量到 RAG（使用多模态 Embedding）
        
        Args:
            image_id: 图片唯一ID
            image_path: 图片文件路径
            caption: 图片描述
            metadata: 元数据（应包含 project_id, material_id 等）
        """
        logger.info(f"🖼️ 同步图片向量到RAG: {image_id}")
        
        try:
            self._init_components()
            
            if not self._initialized:
                logger.warning("⚠️ RAG服务未初始化，跳过同步")
                return
            
            from app.services.multimodal_embedding_service import get_multimodal_embedding_service
            mm_service = get_multimodal_embedding_service()
            
            # 生成图片向量
            image_embedding = mm_service.encode_image(image_path)
            
            if not image_embedding:
                logger.warning(f"⚠️ 图片向量生成失败: {image_path}")
                return
            
            # 文档ID
            doc_id = f"image_{image_id}"
            
            # 先删除旧文档
            await self._delete_document(doc_id)
            
            # 准备元数据
            chunk_metadata = {
                **metadata,
                "doc_id": doc_id,
                "doc_type": "image",  # 标记为图片类型
                "image_path": image_path,
                "caption": caption,
                "content_type": "multimodal"
            }
            
            # 组合描述文本（用于文本检索）
            text_content = f"[图片] {caption}" if caption else f"[图片] {image_path}"
            
            # 添加到向量库
            # 注意：ChromaDB 的 add_texts 会使用配置的 embedding_function
            # 这里我们直接使用文本描述作为检索依据
            self.vectorstore.add_texts(
                texts=[text_content],
                metadatas=[chunk_metadata]
            )
            
            logger.info(f"✅ 图片向量已同步: {image_id}")
            
        except Exception as e:
            logger.error(f"❌ 同步图片向量失败: {str(e)}")
    
    async def search_images(
        self,
        query: str,
        project_id: Optional[int] = None,
        top_k: int = 10
    ) -> List[Dict]:
        """
        搜索本地图片库
        
        Args:
            query: 搜索文本
            project_id: 项目ID（可选，用于过滤）
            top_k: 返回数量
            
        Returns:
            图片列表，每个包含 image_path, caption, score
        """
        logger.info(f"🔍 搜索本地图片: query='{query}', top_k={top_k}")
        
        try:
            self._init_components()
            
            if not self._initialized:
                logger.warning("⚠️ RAG服务未初始化")
                return []
            
            # 构建过滤条件
            where_filter = {"doc_type": "image"}
            if project_id:
                where_filter["project_id"] = project_id
            
            # 如果过滤条件超过一个，需要用 $and
            if len(where_filter) > 1:
                where_filter = {"$and": [{"doc_type": "image"}, {"project_id": project_id}]}
            
            # 执行相似度搜索
            results = self.vectorstore.similarity_search_with_score(
                query=query,
                k=top_k * 2,  # 多取一些，后面过滤
                filter=where_filter
            )
            
            images = []
            for doc, score in results:
                meta = doc.metadata
                if meta.get("doc_type") == "image":
                    images.append({
                        "image_path": meta.get("image_path", ""),
                        "caption": meta.get("caption", ""),
                        "score": float(score),
                        "project_id": meta.get("project_id"),
                        "material_id": meta.get("material_id")
                    })
                    
                    if len(images) >= top_k:
                        break
            
            logger.info(f"✅ 本地图片搜索完成，找到 {len(images)} 张")
            return images
            
        except Exception as e:
            logger.error(f"❌ 搜索本地图片失败: {str(e)}")
            return []
    
    async def search_figures(
        self,
        query: str,
        project_id: Optional[int] = None,
        top_k: int = 10
    ) -> List[Dict]:
        """
        搜索文档中提取的图片（通过描述文本）
        
        Args:
            query: 搜索文本
            project_id: 项目ID（可选）
            top_k: 返回数量
            
        Returns:
            图片列表
        """
        logger.info(f"🔍 搜索文档图片: query='{query}', top_k={top_k}")
        
        try:
            self._init_components()
            
            if not self._initialized:
                return []
            
            # 构建过滤条件
            where_filter = {"doc_type": "figure"}
            if project_id:
                where_filter = {"$and": [{"doc_type": "figure"}, {"project_id": project_id}]}
            
            # 执行搜索
            results = self.vectorstore.similarity_search_with_score(
                query=query,
                k=top_k,
                filter=where_filter
            )
            
            figures = []
            for doc, score in results:
                meta = doc.metadata
                figures.append({
                    "file_path": meta.get("file_path", ""),
                    "caption": doc.page_content,
                    "score": float(score),
                    "material_id": meta.get("material_id"),
                    "page_number": meta.get("page_number")
                })
            
            logger.info(f"✅ 文档图片搜索完成，找到 {len(figures)} 张")
            return figures
            
        except Exception as e:
            logger.error(f"❌ 搜索文档图片失败: {str(e)}")
            return []


# 全局实例
_rag_sync_service = None


def get_rag_sync_service() -> RAGSyncService:
    """获取RAG同步服务单例"""
    global _rag_sync_service
    if _rag_sync_service is None:
        _rag_sync_service = RAGSyncService()
    return _rag_sync_service

