"""
数据库工具函数
提供通用的数据库查询辅助功能
"""
from typing import TypeVar, Type, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.shared.logging import get_logger
logger = get_logger(__name__)

# 泛型类型变量
ModelType = TypeVar('ModelType')


def get_or_404(
    db: Session,
    model: Type[ModelType],
    filter_condition,
    error_message: str = "记录不存在"
) -> ModelType:
    """
    查询数据库记录，如果不存在则抛出404异常
    
    Args:
        db: 数据库会话
        model: SQLAlchemy模型类
        filter_condition: 查询条件（可以是字典或SQLAlchemy表达式）
        error_message: 错误消息
    
    Returns:
        查询到的模型实例
    
    Raises:
        HTTPException: 如果记录不存在
    """
    if isinstance(filter_condition, dict):
        query = db.query(model)
        for key, value in filter_condition.items():
            query = query.filter(getattr(model, key) == value)
        instance = query.first()
    else:
        instance = db.query(model).filter(filter_condition).first()
    
    if not instance:
        logger.warning(f"⚠️ {error_message}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_message
        )
    
    return instance


def get_or_none(
    db: Session,
    model: Type[ModelType],
    filter_condition
) -> Optional[ModelType]:
    """
    查询数据库记录，如果不存在则返回None
    
    Args:
        db: 数据库会话
        model: SQLAlchemy模型类
        filter_condition: 查询条件（可以是字典或SQLAlchemy表达式）
    
    Returns:
        查询到的模型实例，如果不存在则返回None
    """
    if isinstance(filter_condition, dict):
        query = db.query(model)
        for key, value in filter_condition.items():
            query = query.filter(getattr(model, key) == value)
        return query.first()
    else:
        return db.query(model).filter(filter_condition).first()

