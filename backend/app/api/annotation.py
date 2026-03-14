"""
注释管理API
提供注释的增删改查功能
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.models.database import Annotation
from app.utils.logger import logger

router = APIRouter()


class AnnotationCreate(BaseModel):
    """创建注释请求"""
    project_id: int
    position: str
    content: str
    annotation_type: str = "note"


class AnnotationUpdate(BaseModel):
    """更新注释请求"""
    content: Optional[str] = None
    annotation_type: Optional[str] = None
    is_resolved: Optional[bool] = None


@router.post("/annotations")
async def create_annotation(
    request: AnnotationCreate,
    db: Session = Depends(get_db)
):
    """
    创建注释
    
    Args:
        project_id: 项目ID
        position: 位置
        content: 内容
        annotation_type: 类型
    """
    logger.info(f"📝 API: 创建注释 - 项目ID:{request.project_id}")
    
    try:
        annotation = Annotation(
            project_id=request.project_id,
            position=request.position,
            content=request.content,
            annotation_type=request.annotation_type
        )
        
        db.add(annotation)
        db.commit()
        db.refresh(annotation)
        
        logger.info(f"✅ 注释创建成功 - ID:{annotation.id}")
        
        return {
            "id": annotation.id,
            "project_id": annotation.project_id,
            "position": annotation.position,
            "content": annotation.content,
            "annotation_type": annotation.annotation_type,
            "is_resolved": annotation.is_resolved,
            "created_at": annotation.created_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ 创建注释失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/annotations/{project_id}")
async def get_project_annotations(
    project_id: int,
    annotation_type: Optional[str] = None,
    resolved: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    获取项目的所有注释
    
    Args:
        project_id: 项目ID
        annotation_type: 注释类型筛选（可选）
        resolved: 是否已解决筛选（可选）
    """
    logger.info(f"📋 API: 获取项目注释 - 项目ID:{project_id}")
    
    try:
        query = db.query(Annotation).filter(Annotation.project_id == project_id)
        
        if annotation_type:
            query = query.filter(Annotation.annotation_type == annotation_type)
        
        if resolved is not None:
            query = query.filter(Annotation.is_resolved == resolved)
        
        annotations = query.order_by(Annotation.created_at.desc()).all()
        
        result = [
            {
                "id": ann.id,
                "position": ann.position,
                "content": ann.content,
                "annotation_type": ann.annotation_type,
                "is_resolved": ann.is_resolved,
                "created_at": ann.created_at.isoformat(),
                "updated_at": ann.updated_at.isoformat() if ann.updated_at else None
            }
            for ann in annotations
        ]
        
        logger.info(f"✅ 找到 {len(result)} 条注释")
        return {"total": len(result), "annotations": result}
        
    except Exception as e:
        logger.error(f"❌ 获取注释失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/annotations/{annotation_id}")
async def update_annotation(
    annotation_id: int,
    request: AnnotationUpdate,
    db: Session = Depends(get_db)
):
    """
    更新注释
    
    Args:
        annotation_id: 注释ID
        request: 更新内容
    """
    logger.info(f"✏️ API: 更新注释 - ID:{annotation_id}")
    
    try:
        annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
        if not annotation:
            raise HTTPException(status_code=404, detail="注释不存在")
        
        if request.content is not None:
            annotation.content = request.content
        
        if request.annotation_type is not None:
            annotation.annotation_type = request.annotation_type
        
        if request.is_resolved is not None:
            annotation.is_resolved = request.is_resolved
        
        db.commit()
        db.refresh(annotation)
        
        logger.info(f"✅ 注释更新成功")
        
        return {
            "id": annotation.id,
            "content": annotation.content,
            "annotation_type": annotation.annotation_type,
            "is_resolved": annotation.is_resolved,
            "updated_at": annotation.updated_at.isoformat() if annotation.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 更新注释失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/annotations/{annotation_id}")
async def delete_annotation(
    annotation_id: int,
    db: Session = Depends(get_db)
):
    """
    删除注释
    
    Args:
        annotation_id: 注释ID
    """
    logger.info(f"🗑️ API: 删除注释 - ID:{annotation_id}")
    
    try:
        annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
        if not annotation:
            raise HTTPException(status_code=404, detail="注释不存在")
        
        db.delete(annotation)
        db.commit()
        
        logger.info(f"✅ 注释删除成功")
        return {"success": True, "message": "注释已删除"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除注释失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

