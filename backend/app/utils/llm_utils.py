"""
LLM工具函数
统一Agent使用的LLM初始化逻辑
"""
from langchain_openai import ChatOpenAI
from app.config import settings


def get_agent_llm(temperature: float = 0.3) -> ChatOpenAI:
    """
    获取Agent使用的LLM实例（统一初始化）
    
    用于统一所有Agent的LLM初始化逻辑，避免重复代码
    
    Args:
        temperature: 温度参数，默认0.3（适合分析类任务）
        
    Returns:
        ChatOpenAI实例，配置为通义千问模型
    """
    return ChatOpenAI(
        model=settings.QWEN_TEXT_MODEL,
        temperature=temperature,
        openai_api_key=settings.OPENAI_API_KEY,
        openai_api_base=settings.OPENAI_API_BASE
    )
