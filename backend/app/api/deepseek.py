"""
DeepSeek API路由
提供DeepSeek LLM服务的HTTP接口
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional, Literal
import json

from app.services.deepseek_service import get_deepseek_service
from app.shared.logging import get_logger
logger = get_logger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    """聊天请求"""
    messages: List[Dict[str, str]]
    temperature: float = 0.7
    max_tokens: int = 2000
    stream: bool = False


class GenerateDocumentRequest(BaseModel):
    """生成工艺文档请求"""
    intent: str
    context: Optional[Dict] = None
    style: Literal["standard", "detailed", "concise"] = "standard"


class AlignTerminologyRequest(BaseModel):
    """术语对齐请求"""
    text: str
    terminology_db: List[Dict] = []


class CheckComplianceRequest(BaseModel):
    """合规检查请求"""
    document: str
    rules: List[str] = []


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    聊天补全接口
    """
    service = get_deepseek_service()

    if not service.is_available:
        raise HTTPException(
            status_code=503,
            detail="DeepSeek service not available. Please configure DEEPSEEK_API_KEY."
        )

    if request.stream:
        async def generate():
            async for chunk in service.chat_stream(
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            ):
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )

    result = await service.chat(
        messages=request.messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens
    )

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.post("/generate-document")
async def generate_document(request: GenerateDocumentRequest):
    """
    生成工艺文档
    """
    service = get_deepseek_service()

    if not service.is_available:
        raise HTTPException(
            status_code=503,
            detail="DeepSeek service not available. Please configure DEEPSEEK_API_KEY."
        )

    result = await service.generate_process_document(
        intent=request.intent,
        context=request.context or {},
        style=request.style
    )

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.post("/align-terminology")
async def align_terminology(request: AlignTerminologyRequest):
    """
    术语对齐
    """
    service = get_deepseek_service()

    if not service.is_available:
        raise HTTPException(
            status_code=503,
            detail="DeepSeek service not available. Please configure DEEPSEEK_API_KEY."
        )

    result = await service.align_terminology(
        text=request.text,
        terminology_db=request.terminology_db
    )

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.post("/check-compliance")
async def check_compliance(request: CheckComplianceRequest):
    """
    合规检查
    """
    service = get_deepseek_service()

    if not service.is_available:
        raise HTTPException(
            status_code=503,
            detail="DeepSeek service not available. Please configure DEEPSEEK_API_KEY."
        )

    result = await service.check_compliance(
        document=request.document,
        rules=request.rules
    )

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/status")
async def get_status():
    """
    获取DeepSeek服务状态
    """
    service = get_deepseek_service()

    return {
        "available": service.is_available,
        "model": service.model if service.is_available else None,
        "base_url": service.base_url if service.is_available else None
    }
