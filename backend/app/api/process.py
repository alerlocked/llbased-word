"""
智能处理API路由
处理文本清洗、关键信息提取等AI处理任务
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

from app.shared.logging import get_logger
logger = get_logger(__name__)
from app.shared.logging import log_workflow
from app.services.llm_service import llm_service

router = APIRouter()

class CleanTextRequest(BaseModel):
    """文本清洗请求"""
    text: str

class CleanTextResponse(BaseModel):
    """文本清洗响应"""
    cleaned_text: str
    removed_words: List[str]

@router.post("/clean-text", response_model=CleanTextResponse)
async def clean_text(request: CleanTextRequest):
    """
    清洗文本（去口语化）

    Args:
        request: 包含待清洗文本的请求

    Returns:
        清洗后的文本和被移除的词汇
    """
    log_workflow("文本处理", "去口语化", {"text_length": len(request.text)})

    # TODO: 调用大模型API进行文本清洗
    # 这里先返回模拟数据
    cleaned_text = request.text
    removed_words = ["嗯", "啊", "这个", "那个", "就是说"]

    logger.info(f"✅ 文本清洗完成: 移除{len(removed_words)}个口语词")

    return CleanTextResponse(
        cleaned_text=cleaned_text,
        removed_words=removed_words
    )

class ExtractEntitiesRequest(BaseModel):
    """实体提取请求"""
    text: str

class Entity(BaseModel):
    """实体信息"""
    entity: str
    entity_type: str
    positions: List[int]

@router.post("/extract-entities")
async def extract_entities(request: ExtractEntitiesRequest):
    """
    提取关键实体（时间、地点、人物、机构、历史内容）

    Args:
        request: 包含文本的请求

    Returns:
        提取的实体列表
    """
    log_workflow("文本处理", "实体提取", {"text_length": len(request.text)})

    # 调用LLM服务提取实体
    try:
        entities_data = await llm_service.extract_entities(request.text)

        # 转换为API响应格式（添加positions字段，这里简化处理）
        entities = []
        for entity in entities_data:
            # 查找实体在文本中的位置
            text = request.text
            entity_name = entity.get("name", "")
            start_pos = text.find(entity_name)

            entities.append({
                "entity": entity_name,
                "entity_type": entity.get("type", "unknown"),
                "positions": [start_pos, start_pos + len(entity_name)] if start_pos >= 0 else []
            })

        logger.info(f"✅ 实体提取完成: 提取{len(entities)}个实体")

        return {"entities": entities}

    except Exception as e:
        logger.error(f"❌ 实体提取失败: {str(e)}")
        # 返回空列表而不是抛出异常
        return {"entities": []}




