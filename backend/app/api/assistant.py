"""
智能助手API路由
提供意图识别、建议生成、内容生成等功能
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import json
import asyncio

from app.utils.logger import logger
from app.services.llm_service import llm_service, get_llm

router = APIRouter()


# ==================== 请求/响应模型 ====================

class IntentRequest(BaseModel):
    """意图识别请求"""
    text: str = Field(..., description="用户输入的文本")
    context: Optional[Dict[str, Any]] = Field(default=None, description="上下文信息")
    project_id: Optional[int] = Field(default=None, description="项目ID")


class IntentResponse(BaseModel):
    """意图识别响应"""
    intent: str = Field(..., description="识别的意图类型")
    confidence: float = Field(..., description="置信度")
    entities: List[Dict[str, str]] = Field(default=[], description="提取的实体")
    action: Optional[str] = Field(default=None, description="建议的下一步动作")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="提取的参数")


class SuggestionRequest(BaseModel):
    """建议请求"""
    context: str = Field(..., description="当前上下文")
    cursor_position: Optional[int] = Field(default=None, description="光标位置")
    selected_text: Optional[str] = Field(default=None, description="选中的文本")
    document_type: Optional[str] = Field(default="general", description="文档类型")


class Suggestion(BaseModel):
    """单个建议"""
    id: str = Field(..., description="建议ID")
    type: str = Field(..., description="建议类型: rewrite/expand/summarize/translate/correct")
    title: str = Field(..., description="建议标题")
    description: str = Field(..., description="建议描述")
    preview: Optional[str] = Field(default=None, description="预览文本")


class SuggestionsResponse(BaseModel):
    """建议响应"""
    suggestions: List[Suggestion] = Field(..., description="建议列表")
    context_analysis: Optional[str] = Field(default=None, description="上下文分析")


class GenerateRequest(BaseModel):
    """内容生成请求"""
    prompt: str = Field(..., description="生成提示")
    context: Optional[str] = Field(default=None, description="上下文")
    style: Optional[str] = Field(default="professional", description="风格")
    max_length: Optional[int] = Field(default=1000, description="最大长度")
    temperature: Optional[float] = Field(default=0.7, description="温度参数")
    stream: Optional[bool] = Field(default=False, description="是否流式输出")


class GenerateResponse(BaseModel):
    """内容生成响应"""
    content: str = Field(..., description="生成的内容")
    word_count: int = Field(..., description="字数统计")
    style_applied: Optional[str] = Field(default=None, description="应用的风格")


# ==================== 意图识别API ====================

@router.post("/intent", response_model=IntentResponse)
async def recognize_intent(request: IntentRequest):
    """
    识别用户输入的意图

    支持的意图类型:
    - create: 创建新文档
    - edit: 编辑现有内容
    - query: 查询信息
    - export: 导出文档
    - help: 请求帮助
    - material: 素材相关
    - style: 风格调整
    - unknown: 无法识别
    """
    try:
        logger.info(f"🎯 意图识别: {request.text[:50]}...")

        # 构建提示词
        prompt = f"""分析以下用户输入，识别其意图并提取关键信息。

用户输入: {request.text}

请按以下JSON格式输出:
{{
    "intent": "意图类型(create/edit/query/export/help/material/style/unknown)",
    "confidence": 0.0-1.0的置信度,
    "entities": [{{"name": "实体名", "type": "实体类型"}}],
    "action": "建议的下一步动作",
    "parameters": {{提取的关键参数}}
}}

意图类型说明:
- create: 创建新文档或项目
- edit: 编辑、修改、重写现有内容
- query: 查询信息、搜索、检索
- export: 导出、下载、保存
- help: 请求帮助、询问如何操作
- material: 素材上传、管理、查看
- style: 风格调整、格式修改
- unknown: 无法确定意图

只输出JSON，不要包含其他内容。"""

        # 调用LLM
        result = await llm_service.generate_text(prompt, temperature=0.3, max_tokens=500)

        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result.get("error", "LLM调用失败"))

        # 解析响应
        response_text = result["content"].strip()

        # 清理可能的markdown标记
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        try:
            intent_data = json.loads(response_text)
        except json.JSONDecodeError:
            # 如果解析失败，返回默认意图
            intent_data = {
                "intent": "unknown",
                "confidence": 0.0,
                "entities": [],
                "action": None,
                "parameters": None
            }

        logger.info(f"✅ 意图识别结果: {intent_data['intent']} (置信度: {intent_data['confidence']})")

        return IntentResponse(**intent_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 意图识别失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"意图识别失败: {str(e)}")


# ==================== 建议API ====================

@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions(
    context: str = Query(..., description="当前上下文"),
    cursor_position: Optional[int] = Query(None, description="光标位置"),
    selected_text: Optional[str] = Query(None, description="选中的文本"),
    document_type: str = Query("general", description="文档类型")
):
    """
    获取智能建议

    根据当前上下文和选中内容，提供相关的编辑建议
    """
    try:
        logger.info(f"💡 获取建议: 上下文长度={len(context)}, 选中={bool(selected_text)}")

        suggestions = []

        # 根据是否有选中文本提供不同建议
        if selected_text:
            # 有选中文本的建议
            suggestions = [
                Suggestion(
                    id=str(uuid.uuid4())[:8],
                    type="rewrite",
                    title="重写选中内容",
                    description="用不同方式表达相同意思",
                    preview=None
                ),
                Suggestion(
                    id=str(uuid.uuid4())[:8],
                    type="expand",
                    title="扩展内容",
                    description="添加更多细节和说明",
                    preview=None
                ),
                Suggestion(
                    id=str(uuid.uuid4())[:8],
                    type="summarize",
                    title="精简总结",
                    description="提炼核心要点，简化表述",
                    preview=None
                ),
                Suggestion(
                    id=str(uuid.uuid4())[:8],
                    type="correct",
                    title="检查修正",
                    description="检查语法和用词问题",
                    preview=None
                )
            ]
        else:
            # 无选中文本的通用建议
            suggestions = [
                Suggestion(
                    id=str(uuid.uuid4())[:8],
                    type="expand",
                    title="继续写作",
                    description="基于当前内容继续生成",
                    preview=None
                ),
                Suggestion(
                    id=str(uuid.uuid4())[:8],
                    type="summarize",
                    title="生成摘要",
                    description="为当前段落生成摘要",
                    preview=None
                )
            ]

        # 生成上下文分析
        context_analysis = f"检测到{document_type}类型的文档，"
        if selected_text:
            context_analysis += f"已选中 {len(selected_text)} 个字符的内容。"
        else:
            context_analysis += f"当前上下文包含 {len(context)} 个字符。"

        return SuggestionsResponse(
            suggestions=suggestions,
            context_analysis=context_analysis
        )

    except Exception as e:
        logger.error(f"❌ 获取建议失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取建议失败: {str(e)}")


# ==================== 内容生成API ====================

@router.post("/generate", response_model=GenerateResponse)
async def generate_content(request: GenerateRequest):
    """
    生成内容

    根据提示词和上下文生成新内容
    """
    try:
        logger.info(f"✍️ 内容生成: 提示长度={len(request.prompt)}, 风格={request.style}")

        # 构建完整提示
        full_prompt = request.prompt
        if request.context:
            full_prompt = f"上下文:\n{request.context}\n\n任务:\n{request.prompt}"

        if request.style and request.style != "default":
            style_guide = {
                "professional": "使用专业、正式的商务语言",
                "casual": "使用轻松、口语化的表达",
                "technical": "使用技术性、精确的术语",
                "creative": "使用富有创意和想象力的表达"
            }
            if request.style in style_guide:
                full_prompt = f"{style_guide[request.style]}。\n\n{full_prompt}"

        # 调用LLM
        result = await llm_service.generate_text(
            full_prompt,
            temperature=request.temperature,
            max_tokens=request.max_length * 2  # 预留token余量
        )

        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result.get("error", "LLM调用失败"))

        content = result["content"]
        word_count = len(content)

        logger.info(f"✅ 内容生成完成: {word_count}字")

        return GenerateResponse(
            content=content,
            word_count=word_count,
            style_applied=request.style if request.style != "default" else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 内容生成失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"内容生成失败: {str(e)}")


@router.post("/generate-stream")
async def generate_content_stream(request: GenerateRequest):
    """
    流式生成内容 (SSE)

    实时返回生成的内容
    """
    try:
        logger.info(f"✍️ 流式生成: 提示长度={len(request.prompt)}")

        async def generate():
            """SSE生成器"""
            try:
                # 构建完整提示
                full_prompt = request.prompt
                if request.context:
                    full_prompt = f"上下文:\n{request.context}\n\n任务:\n{request.prompt}"

                # 获取LangChain兼容的LLM
                llm = get_llm()

                # 使用LangChain的流式生成
                full_content = ""
                async for chunk in llm.astream(full_prompt):
                    content_piece = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_content += content_piece

                    # 发送SSE事件
                    yield f"data: {json.dumps({'content': content_piece, 'done': False})}\n\n"

                    # 添加小延迟使流式效果更明显
                    await asyncio.sleep(0.01)

                # 发送完成事件
                yield f"data: {json.dumps({'content': '', 'done': True, 'word_count': len(full_content)})}\n\n"

                logger.info(f"✅ 流式生成完成: {len(full_content)}字")

            except Exception as e:
                logger.error(f"❌ 流式生成错误: {str(e)}")
                yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except Exception as e:
        logger.error(f"❌ 流式生成启动失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"流式生成失败: {str(e)}")
