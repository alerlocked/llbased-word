"""
自动同步辅助函数
处理工艺文件自动收集和RAG自动同步
"""
from sqlalchemy.orm import Session
from typing import Optional

from app.shared.logging import get_logger
logger = get_logger(__name__)


async def auto_save_to_style_library(
    user_id: int,
    title: str,
    content: str,
    source: str,
    source_id: Optional[int],
    db: Session
):
    """
    自动保存文章到风格库

    Args:
        user_id: 用户ID
        title: 文章标题
        content: 文章内容
        source: 来源（agent_generated/editor_saved/document）
        source_id: 来源ID
        db: 数据库会话
    """
    try:
        # TODO: 实现风格库保存逻辑
        logger.info(f"📝 自动保存到风格库: {title}")
    except Exception as e:
        logger.warning(f"⚠️ 自动保存到风格库失败: {str(e)}")


async def auto_sync_to_rag(
    doc_id: str,
    doc_type: str,
    content: str,
    metadata: dict
):
    """
    自动同步内容到RAG知识库

    Args:
        doc_id: 文档ID
        doc_type: 文档类型（document/article/project）
        content: 文档内容
        metadata: 元数据
    """
    try:
        from app.services.rag_sync_service import get_rag_sync_service

        rag_service = get_rag_sync_service()

        if doc_type == "document":
            await rag_service.sync_document(
                doc_id=doc_id,
                content=content,
                metadata=metadata
            )
        elif doc_type == "article":
            await rag_service.sync_article(
                article_id=metadata.get("article_id"),
                title=metadata.get("title", ""),
                content=content,
                metadata=metadata
            )
        elif doc_type == "project":
            await rag_service.sync_project_content(
                project_id=metadata.get("project_id"),
                content=content,
                metadata=metadata
            )

        logger.info(f"✅ 内容已自动同步到RAG: doc_id={doc_id}")

    except Exception as e:
        logger.warning(f"⚠️ 自动同步到RAG失败: {str(e)}")
