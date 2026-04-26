"""
Context API - 上下文服务 API 端点

提供 ContextService 的 HTTP 接口（模板、示例、上下文构建）
用户画像管理已迁移到 /api/profile
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging

from app.services.context_service import ContextService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["上下文服务"])

# ContextService 实例（单例）
_context_service: Optional[ContextService] = None


def get_context_service() -> ContextService:
    """获取 ContextService 单例"""
    global _context_service
    if _context_service is None:
        # 使用项目根目录作为基础路径
        from app.config import settings
        base_path = settings.PROJECT_ROOT
        _context_service = ContextService(base_path=base_path)
    return _context_service


# ========================================
# Request/Response Models
# ========================================

class BuildContextRequest(BaseModel):
    """构建上下文请求"""
    user_id: str
    domain: str
    doc_type: str


class TemplateResponse(BaseModel):
    """模板响应"""
    id: str
    domain: str
    doc_type: str
    structure: List[str]
    required_fields: List[str]
    style_guide: Dict[str, Any]


class BuildContextResponse(BaseModel):
    """构建上下文响应"""
    context: str
    user_id: str
    domain: str
    doc_type: str


class ExamplesResponse(BaseModel):
    """示例响应"""
    examples: List[Dict[str, Any]]
    domain: str
    count: int


# ========================================
# API Endpoints
# ========================================

@router.get("/template")
async def get_template(
    domain: str = Query(..., description="领域"),
    doc_type: str = Query(..., description="文档类型")
):
    """
    获取文档模板

    返回文档的结构、必填字段和样式指南
    """
    try:
        service = get_context_service()
        template = service.load_template(domain, doc_type)

        logger.info("get_template_success", domain=domain, doc_type=doc_type)

        return TemplateResponse(
            id=template.id,
            domain=template.domain,
            doc_type=template.doc_type,
            structure=template.structure,
            required_fields=template.required_fields,
            style_guide=template.style_guide
        )
    except Exception as e:
        logger.error("get_template_failed", error=str(e), domain=domain, doc_type=doc_type)
        raise HTTPException(status_code=500, detail=f"加载模板失败: {str(e)}")


@router.get("/examples")
async def get_examples(
    domain: str = Query(..., description="领域"),
    limit: int = Query(3, ge=1, le=10, description="最大数量")
):
    """
    获取示例文档

    返回指定领域的示例文档列表
    """
    try:
        service = get_context_service()
        examples = service.load_examples(domain, limit)

        logger.info("get_examples_success", domain=domain, count=len(examples))

        return ExamplesResponse(
            examples=[e.__dict__ for e in examples],
            domain=domain,
            count=len(examples)
        )
    except Exception as e:
        logger.error("get_examples_failed", error=str(e), domain=domain)
        raise HTTPException(status_code=500, detail=f"加载示例失败: {str(e)}")


@router.post("/build")
async def build_context(request: BuildContextRequest):
    """
    构建完整上下文

    整合模板、画像、示例，生成完整的上下文字符串
    供 Writing Agent 使用
    """
    try:
        service = get_context_service()
        context = service.build_context(
            user_id=request.user_id,
            domain=request.domain,
            doc_type=request.doc_type
        )

        logger.info(
            "build_context_success",
            user_id=request.user_id,
            domain=request.domain,
            doc_type=request.doc_type,
            context_length=len(context)
        )

        return BuildContextResponse(
            context=context,
            user_id=request.user_id,
            domain=request.domain,
            doc_type=request.doc_type
        )
    except Exception as e:
        logger.error(
            "build_context_failed",
            error=str(e),
            user_id=request.user_id,
            domain=request.domain
        )
        raise HTTPException(status_code=500, detail=f"构建上下文失败: {str(e)}")
