"""
API依赖注入函数
提供通用的依赖注入函数，减少重复代码
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.database import CreationProject
from app.utils.logger import logger
from app.utils.db_utils import get_or_404


def verify_project(project_id: int, db: Session = Depends(get_db)) -> CreationProject:
    """
    验证项目是否存在，如果不存在则抛出404异常
    用作FastAPI依赖注入函数
    
    Args:
        project_id: 项目ID
        db: 数据库会话
    
    Returns:
        CreationProject实例
    
    Raises:
        HTTPException: 如果项目不存在
    """
    return get_or_404(
        db=db,
        model=CreationProject,
        filter_condition=CreationProject.id == project_id,
        error_message="项目不存在"
    )

