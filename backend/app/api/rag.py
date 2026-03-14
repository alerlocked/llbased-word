"""
RAG知识库管理API
管理向量知识库的文档、检索和同步
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.services.rag_sync_service import get_rag_sync_service
from app.utils.logger import logger

# 创建路由
router = APIRouter()


# 请求/响应模型
class UploadDocumentResponse(BaseModel):
    """上传文档响应"""
    doc_id: str
    filename: str
    message: str


class SyncRequest(BaseModel):
    """同步请求"""
    sync_type: str  # articles/projects/all


class DeleteDocumentRequest(BaseModel):
    """删除文档请求"""
    doc_id: str


@router.post("/upload-document", response_model=UploadDocumentResponse)
async def upload_reference_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    上传参考文档到RAG知识库
    
    Args:
        file: 上传的文件（TXT、Word、PDF）
        db: 数据库会话
    
    Returns:
        上传结果
    """
    logger.info(f"📤 上传参考文档到RAG: {file.filename}")
    
    try:
        rag_service = get_rag_sync_service()
        
        # 读取文件内容
        file_content = await file.read()
        
        # 解析文档内容
        text_content = rag_service.parse_document_file(file_content, file.filename)
        
        # 生成文档ID
        doc_id = f"uploaded_{file.filename}_{int(datetime.now().timestamp())}"
        
        # 准备元数据
        metadata = {
            "filename": file.filename,
            "upload_time": str(datetime.now()),
            "file_size": len(file_content)
        }
        
        # 同步到RAG
        await rag_service.sync_uploaded_document(
            doc_id=doc_id,
            filename=file.filename,
            content=text_content,
            metadata=metadata
        )
        
        logger.info(f"✅ 参考文档已上传到RAG: {file.filename}")
        
        return {
            "doc_id": doc_id,
            "filename": file.filename,
            "message": "文档上传成功"
        }
        
    except Exception as e:
        logger.error(f"❌ 上传参考文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.post("/sync")
async def sync_to_rag(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    手动触发同步到RAG
    
    Args:
        request: 同步请求
        background_tasks: 后台任务
        db: 数据库会话
    
    Returns:
        同步任务信息
    """
    logger.info(f"🔄 触发RAG同步: {request.sync_type}")
    
    try:
        rag_service = get_rag_sync_service()

        # 添加后台同步任务
        if request.sync_type == "articles":
            background_tasks.add_task(rag_service.sync_all_articles, db)
            message = "文章同步任务已启动"
        elif request.sync_type == "projects":
            background_tasks.add_task(rag_service.sync_all_projects, db)
            message = "项目内容同步任务已启动"
        elif request.sync_type == "all":
            background_tasks.add_task(_sync_all_task, rag_service, db)
            message = "全量同步任务已启动"
        else:
            raise HTTPException(status_code=400, detail="不支持的同步类型")
        
        logger.info(f"✅ {message}")
        
        return {
            "message": message,
            "sync_type": request.sync_type
        }
        
    except Exception as e:
        logger.error(f"❌ 启动同步任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动失败: {str(e)}")


async def _sync_all_task(rag_service, db: Session):
    """全量同步任务"""
    logger.info("🚀 开始全量同步...")

    try:
        await rag_service.sync_all_articles(db)
        await rag_service.sync_all_projects(db)

        logger.info("✅ 全量同步完成")

    except Exception as e:
        logger.error(f"❌ 全量同步失败: {str(e)}")


@router.delete("/document")
async def delete_document(
    request: DeleteDocumentRequest,
    db: Session = Depends(get_db)
):
    """
    删除RAG文档并级联删除相关数据库记录
    
    Args:
        request: 删除请求
        db: 数据库会话
    
    Returns:
        删除结果
    """
    logger.info(f"🗑️ 删除RAG文档并级联删除相关记录: {request.doc_id}")
    
    try:
        from app.models.database import Material, CreationProject, MaterialPage, Figure

        rag_service = get_rag_sync_service()

        # 解析 doc_id: "document_10" → type="document", id=10
        doc_parts = request.doc_id.split("_")
        if len(doc_parts) < 2:
            raise HTTPException(status_code=400, detail="无效的文档ID格式")

        doc_type = doc_parts[0]
        try:
            record_id = int(doc_parts[1])
        except ValueError:
            # 对于非数字ID（如上传的文档），只删除RAG记录
            await rag_service.delete_document_by_id(request.doc_id)
            return {
                "message": "文档已删除",
                "doc_id": request.doc_id
            }

        # 1. 删除 ChromaDB 记录
        await rag_service.delete_document_by_id(request.doc_id)
        logger.info(f"✅ 已从ChromaDB删除: {request.doc_id}")

        # 2. 级联删除数据库记录
        deleted_items = []

        if doc_type == "document":
            # 删除文档页面记录
            page = db.query(MaterialPage).filter(MaterialPage.id == record_id).first()
            if page:
                # 删除关联的图表
                figures = db.query(Figure).filter(Figure.material_id == page.material_id).all()
                for fig in figures:
                    db.delete(fig)
                    deleted_items.append(f"Figure#{fig.id}")

                db.delete(page)
                deleted_items.append(f"MaterialPage#{record_id}")
                logger.info(f"✅ 已删除文档页面及 {len(figures)} 个图表")

        elif doc_type == "figure":
            # 删除图表记录
            figure = db.query(Figure).filter(Figure.id == record_id).first()
            if figure:
                db.delete(figure)
                deleted_items.append(f"Figure#{record_id}")
                logger.info(f"✅ 已删除图表记录")

        db.commit()
        
        logger.info(f"✅ 级联删除完成: {request.doc_id}, 删除项: {deleted_items}")
        
        return {
            "message": "文档及相关记录已删除",
            "doc_id": request.doc_id,
            "deleted_items": deleted_items
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 删除文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.get("/statistics")
async def get_rag_statistics(db: Session = Depends(get_db)):
    """
    获取RAG知识库统计信息
    
    Args:
        db: 数据库会话
    
    Returns:
        统计信息
    """
    logger.info("📊 获取RAG知识库统计信息")
    
    try:
        rag_service = get_rag_sync_service()
        
        stats = rag_service.get_statistics()
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ 获取统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/documents")
async def list_rag_documents(
    doc_type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    列出RAG知识库中的文档
    
    Args:
        doc_type: 文档类型筛选
        limit: 返回数量限制
        db: 数据库会话
    
    Returns:
        文档列表
    """
    logger.info(f"📚 列出RAG文档, doc_type={doc_type}")
    
    try:
        rag_service = get_rag_sync_service()
        rag_service._init_components()
        
        if not rag_service._initialized:
            return {
                "documents": [],
                "total": 0,
                "message": "RAG服务未初始化"
            }
        
        # 获取所有文档
        all_docs = rag_service.vectorstore.get()
        
        if not all_docs or not all_docs.get('metadatas'):
            return {
                "documents": [],
                "total": 0
            }
        
        # 按doc_id分组
        doc_map = {}
        for i, metadata in enumerate(all_docs['metadatas']):
            doc_id = metadata.get('doc_id', '')
            current_doc_type = metadata.get('doc_type', 'unknown')
            
            # 类型筛选
            if doc_type and current_doc_type != doc_type:
                continue
            
            if doc_id not in doc_map:
                doc_map[doc_id] = {
                    "doc_id": doc_id,
                    "doc_type": current_doc_type,
                    "metadata": metadata,
                    "chunk_count": 0
                }
            
            doc_map[doc_id]["chunk_count"] += 1
        
        # 转换为列表
        documents = list(doc_map.values())[:limit]
        
        return {
            "documents": documents,
            "total": len(doc_map)
        }
        
    except Exception as e:
        logger.error(f"❌ 列出文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"列出失败: {str(e)}")


@router.get("/health")
async def rag_health_check():
    """
    RAG服务健康检查
    
    Returns:
        服务状态
    """
    try:
        rag_service = get_rag_sync_service()
        rag_service._init_components()
        
        if rag_service._initialized:
            return {
                "status": "healthy",
                "message": "RAG服务正常运行"
            }
        else:
            return {
                "status": "unhealthy",
                "message": "RAG服务未初始化"
            }
            
    except Exception as e:
        logger.error(f"❌ 健康检查失败: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

