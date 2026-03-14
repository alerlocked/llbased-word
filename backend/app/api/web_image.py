"""
网络图片管理API
提供图片搜索、下载、管理功能
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path

from app.database import get_db
from app.models.database import WebImage
from app.agents.tools.image_search import get_image_search_tool
from app.services.image_relevance_service import get_image_relevance_service
from app.utils.logger import logger
from app.config import settings

router = APIRouter()


class ImageSearchRequest(BaseModel):
    """图片搜索请求"""
    keyword: str
    count: int = 5
    safe_search: bool = True


class ImageRelevanceRequest(BaseModel):
    """图片相关性评估请求"""
    image_id: int
    topic: str
    context: Optional[str] = None


@router.post("/search")
async def search_images(
    request: ImageSearchRequest,
    db: Session = Depends(get_db)
):
    """
    搜索网络图片
    
    Args:
        keyword: 搜索关键词
        count: 返回数量
        safe_search: 安全搜索
    """
    logger.info(f"🔍 API: 搜索图片 - {request.keyword}")
    
    try:
        image_tool = get_image_search_tool()
        
        # 搜索并下载图片
        images = await image_tool.search_and_download(
            request.keyword,
            request.count,
            request.safe_search
        )
        
        # 保存到数据库
        saved_images = []
        for img_data in images:
            # 检查是否已存在（根据file_hash）
            if 'file_hash' in img_data:
                existing = db.query(WebImage).filter(
                    WebImage.file_hash == img_data['file_hash']
                ).first()
                
                if existing:
                    saved_images.append({
                        "id": existing.id,
                        "keyword": existing.keyword,
                        "local_path": existing.local_path,
                        "title": existing.title,
                        "source": existing.source_website,
                        "existed": True
                    })
                    continue
            
            # 创建新记录
            web_image = WebImage(
                keyword=request.keyword,
                original_url=img_data.get('url', ''),
                thumbnail_url=img_data.get('thumbnail_url', ''),
                local_path=img_data.get('local_path', ''),
                title=img_data.get('title', ''),
                source_website=img_data.get('source', ''),
                width=img_data.get('width', 0),
                height=img_data.get('height', 0),
                file_size=img_data.get('file_size', 0),
                file_hash=img_data.get('file_hash', ''),
                description=None,  # 稍后评估
                relevance_score=None,
                is_verified=False
            )
            
            db.add(web_image)
            db.commit()
            db.refresh(web_image)
            
            saved_images.append({
                "id": web_image.id,
                "keyword": web_image.keyword,
                "local_path": web_image.local_path,
                "title": web_image.title,
                "source": web_image.source_website,
                "existed": False
            })
        
        logger.info(f"✅ 成功保存 {len(saved_images)} 张图片")
        
        return {
            "success": True,
            "total": len(saved_images),
            "images": saved_images
        }
        
    except Exception as e:
        logger.error(f"❌ 图片搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate")
async def evaluate_image_relevance(
    request: ImageRelevanceRequest,
    db: Session = Depends(get_db)
):
    """
    评估图片与主题的相关性
    
    Args:
        image_id: 图片ID
        topic: 文章主题
        context: 上下文（可选）
    """
    logger.info(f"🎨 API: 评估图片相关性 - ID:{request.image_id}")
    
    try:
        # 查找图片
        web_image = db.query(WebImage).filter(WebImage.id == request.image_id).first()
        if not web_image:
            raise HTTPException(status_code=404, detail="图片不存在")
        
        # 获取本地路径
        image_path = settings.BASE_DIR / web_image.local_path
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="图片文件不存在")
        
        # 评估相关性
        relevance_service = get_image_relevance_service()
        evaluation = await relevance_service.evaluate_relevance(
            image_path,
            request.topic,
            request.context
        )
        
        # 更新数据库
        web_image.relevance_score = evaluation['relevance_score']
        web_image.description = evaluation['description']
        web_image.is_verified = True
        db.commit()
        
        logger.info(f"✅ 相关性评估完成: {evaluation['relevance_score']:.2f}")
        
        return {
            "success": True,
            "image_id": web_image.id,
            "evaluation": evaluation
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 相关性评估失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_web_images(
    keyword: Optional[str] = None,
    verified_only: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    获取网络图片列表
    
    Args:
        keyword: 关键词筛选（可选）
        verified_only: 只返回已验证的
        skip: 跳过数量
        limit: 返回数量
    """
    logger.info(f"📋 API: 获取网络图片列表")
    
    try:
        query = db.query(WebImage)
        
        # 筛选条件
        if keyword:
            query = query.filter(WebImage.keyword.contains(keyword))
        
        if verified_only:
            query = query.filter(WebImage.is_verified == True)
        
        # 按下载时间倒序
        query = query.order_by(WebImage.download_time.desc())
        
        # 分页
        total = query.count()
        images = query.offset(skip).limit(limit).all()
        
        result = {
            "total": total,
            "skip": skip,
            "limit": limit,
            "images": [
                {
                    "id": img.id,
                    "keyword": img.keyword,
                    "title": img.title,
                    "local_path": img.local_path,
                    "source": img.source_website,
                    "width": img.width,
                    "height": img.height,
                    "file_size": img.file_size,
                    "relevance_score": img.relevance_score,
                    "description": img.description,
                    "is_verified": img.is_verified,
                    "download_time": img.download_time.isoformat() if img.download_time else None
                }
                for img in images
            ]
        }
        
        return result
        
    except Exception as e:
        logger.error(f"❌ 获取图片列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{image_id}")
async def delete_web_image(
    image_id: int,
    db: Session = Depends(get_db)
):
    """
    删除网络图片
    
    Args:
        image_id: 图片ID
    """
    logger.info(f"🗑️ API: 删除网络图片 - ID:{image_id}")
    
    try:
        web_image = db.query(WebImage).filter(WebImage.id == image_id).first()
        if not web_image:
            raise HTTPException(status_code=404, detail="图片不存在")
        
        # 删除本地文件
        try:
            image_path = settings.BASE_DIR / web_image.local_path
            if image_path.exists():
                image_path.unlink()
                logger.info(f"✓ 删除本地文件: {image_path}")
        except Exception as e:
            logger.warning(f"⚠️ 删除本地文件失败: {str(e)}")
        
        # 删除数据库记录
        db.delete(web_image)
        db.commit()
        
        logger.info(f"✅ 图片删除成功")
        
        return {"success": True, "message": "图片已删除"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除图片失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

