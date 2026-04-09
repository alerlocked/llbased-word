"""
工艺文件项目 - 数据模型

注意：此文件仅包含工艺文件相关的模型
遗留的新闻写作模型已移至 schemas_news_legacy.py
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


# ========================================
# 通用基础模型
# ========================================

class BaseResponse(BaseModel):
    """通用响应模型"""
    success: bool = True
    message: str = ""
    data: Optional[Dict[str, Any]] = None


# ========================================
# 工艺文件相关模型（按需添加）
# ========================================

# 兼容旧代码的占位符（将被逐步移除）
class TaskPlan(BaseModel):
    """任务计划（兼容占位符 - 将被移除）"""
    user_intent: str = ""
    outline: List[str] = Field(default=[])
