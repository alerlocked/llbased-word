"""
大语言模型服务
使用通义千问qwen-plus模型进行文本生成
"""
import time
from typing import List, Dict, Optional, Literal, AsyncGenerator
import httpx
from openai import AsyncOpenAI

from app.config import settings
from app.shared.logging import get_logger
logger = get_logger(__name__)
from app.shared.logging import log_api_call

class QwenLLMService:
    """通义千问文本生成服务"""

    def __init__(self):
        """
        初始化通义千问客户端
        使用OpenAI兼容格式调用
        Supports tier-specific base URLs for local deployment.
        """
        self.api_key = settings.DASHSCOPE_API_KEY
        self._default_base_url = settings.DASHSCOPE_BASE_URL

        # Tier-specific clients (lazy init)
        # timeout: 30s connect (model server may be loading), 300s read (inference can be slow)
        self._timeout = httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=30.0)

        self._complex_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=settings.DASHSCOPE_BASE_URL_COMPLEX or self._default_base_url,
            timeout=self._timeout,
            max_retries=1,
        )
        self._simple_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=settings.DASHSCOPE_BASE_URL_SIMPLE or self._default_base_url,
            timeout=self._timeout,
            max_retries=1,
        )

        self.model = settings.QWEN_TEXT_MODEL

    def _get_client(self, tier: str = "complex"):
        """Get the OpenAI client for the given tier."""
        return self._simple_client if tier == "simple" else self._complex_client

    def _get_model(self, tier: str = "complex"):
        """Get the model name for the given tier."""
        return (
            settings.MODEL_TIER_SIMPLE if tier == "simple"
            else settings.MODEL_TIER_COMPLEX
        )
        
    async def generate_article(
        self,
        content: str,
        article_type: Literal["news", "feature", "investigation"],
        word_count: int = 500
    ) -> Dict[str, str]:
        """
        基于素材内容生成稿件

        Args:
            content: 素材文本内容
            article_type: 稿件类型（快讯/特写/调查报道）
            word_count: 目标字数

        Returns:
            包含title和content的字典
        """
        start_time = time.time()

        try:
            # 根据稿件类型构建不同的提示词
            article_type_prompts = {
                "news": {
                    "name": "新闻快讯",
                    "style": "简洁明快，突出时效性和新闻价值，采用倒金字塔结构",
                    "requirements": "标题简洁有力，导语概括核心信息，正文层层递进补充细节"
                },
                "feature": {
                    "name": "人物特写",
                    "style": "生动细腻，注重细节描写和情感表达，展现人物特点",
                    "requirements": "标题富有感染力，开头引人入胜，通过具体事例和细节刻画人物形象"
                },
                "investigation": {
                    "name": "调查报道",
                    "style": "深入客观，逻辑严密，数据详实，揭示问题本质",
                    "requirements": "标题点明核心问题，结构清晰，论据充分，提供背景分析和多方观点"
                }
            }

            type_info = article_type_prompts[article_type]

            # 构建提示词
            prompt = f"""你是一位专业的记者和编辑。请基于以下素材内容，撰写一篇{type_info['name']}。

【素材内容】
{content}

【写作要求】
1. 稿件类型：{type_info['name']}
2. 写作风格：{type_info['style']}
3. 具体要求：{type_info['requirements']}
4. 目标字数：约{word_count}字
5. 输出格式：
   - 第一行：文章标题（不要包含"标题："等前缀）
   - 空一行
   - 正文内容（分段清晰，每段之间空一行）

【注意事项】
- 确保信息准确，不添加转写内容中没有的信息
- 语言流畅自然，符合新闻写作规范
- 如果转写内容不足以支撑完整稿件，请基于现有信息尽力完成
- 直接输出标题和正文，不要包含任何说明性文字

请开始撰写："""

            logger.info(f"📝 开始生成{type_info['name']}稿件...")
            
            # 调用通义千问API
            response = await self._get_client("complex").chat.completions.create(
                model=self._get_model("complex"),
                messages=[
                    {"role": "system", "content": "你是一位经验丰富的专业新闻记者和编辑，擅长将采访内容整理成高质量的新闻稿件。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # 解析响应
            generated_text = response.choices[0].message.content.strip()
            
            # 分离标题和正文
            lines = generated_text.split('\n')
            title = lines[0].strip()
            
            # 移除标题可能包含的前缀
            for prefix in ["标题：", "标题:", "# ", "## "]:
                if title.startswith(prefix):
                    title = title[len(prefix):].strip()
            
            # 提取正文（跳过空行）
            content_lines = []
            for line in lines[1:]:
                if line.strip():
                    content_lines.append(line.strip())
            content = '\n\n'.join(content_lines)
            
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("通义千问LLM", f"生成{type_info['name']}", "success", duration_ms)
            
            logger.info(f"✅ 稿件生成完成: 标题《{title}》, 耗时{duration_ms:.2f}ms")
            
            return {
                "title": title,
                "content": content
            }
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("通义千问LLM", "生成稿件", "error", duration_ms)
            logger.error(f"❌ 稿件生成失败: {str(e)}")
            raise
    
    async def summarize_text(
        self,
        text: str,
        max_length: int = 200
    ) -> str:
        """
        生成文本摘要
        
        Args:
            text: 原始文本
            max_length: 摘要最大长度
        
        Returns:
            摘要文本
        """
        start_time = time.time()
        
        try:
            logger.info(f"📄 开始生成文本摘要...")
            
            prompt = f"""请为以下文本生成一个简洁的摘要，要求：
1. 提取核心信息和关键观点
2. 长度控制在{max_length}字以内
3. 语言简洁明了
4. 直接输出摘要内容，不要包含"摘要："等前缀

【原文】
{text}

请生成摘要："""
            
            response = await self._get_client("complex").chat.completions.create(
                model=self._get_model("complex"),
                messages=[
                    {"role": "system", "content": "你是一位专业的文本摘要专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=500
            )
            
            summary = response.choices[0].message.content.strip()
            
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("通义千问LLM", "生成摘要", "success", duration_ms)
            
            logger.info(f"✅ 摘要生成完成, 耗时{duration_ms:.2f}ms")
            
            return summary
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("通义千问LLM", "生成摘要", "error", duration_ms)
            logger.error(f"❌ 摘要生成失败: {str(e)}")
            raise
    
    async def extract_entities(
        self,
        text: str
    ) -> List[Dict[str, str]]:
        """
        从文本中提取实体（人名、地名、机构名等）
        
        Args:
            text: 原始文本
        
        Returns:
            实体列表，每个实体包含name和type
        """
        start_time = time.time()
        
        try:
            logger.info(f"🔍 开始提取实体...")
            
            prompt = f"""请从以下文本中提取关键实体信息，包括：
- 人名（person）
- 地名（location）
- 机构组织（organization）
- 时间（time）
- 事件（event）

要求：
1. 只提取明确出现的实体
2. 按JSON格式输出，格式如下：
[
  {{"name": "实体名称", "type": "实体类型"}},
  ...
]
3. 直接输出JSON数组，不要包含任何其他文字

【文本】
{text}

请提取实体："""
            
            response = await self._get_client("complex").chat.completions.create(
                model=self._get_model("complex"),
                messages=[
                    {"role": "system", "content": "你是一位专业的信息提取专家，擅长从文本中识别和提取关键实体。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 尝试解析JSON
            import json
            # 移除可能的markdown代码块标记
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            
            entities = json.loads(result_text.strip())
            
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("通义千问LLM", "提取实体", "success", duration_ms)
            
            logger.info(f"✅ 实体提取完成: 共{len(entities)}个实体, 耗时{duration_ms:.2f}ms")
            
            return entities
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("通义千问LLM", "提取实体", "error", duration_ms)
            logger.error(f"❌ 实体提取失败: {str(e)}")
            # 返回空列表而不是抛出异常
            return []
    
    async def generate_text(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tier: Literal["simple", "complex"] = "complex",
    ) -> Dict:
        """
        通用文本生成方法

        Args:
            prompt: 提示词
            temperature: 温度参数
            max_tokens: 最大token数
            tier: "simple" for QA/lookup, "complex" for generation/review

        Returns:
            包含status和content的字典
        """
        start_time = time.time()

        model = (
            settings.MODEL_TIER_SIMPLE if tier == "simple"
            else settings.MODEL_TIER_COMPLEX
        )

        try:
            response = await self._get_client(tier).chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            content = response.choices[0].message.content.strip()
            
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("通义千问LLM", "文本生成", "success", duration_ms)
            
            return {
                "status": "success",
                "content": content
            }
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("通义千问LLM", "文本生成", "error", duration_ms)
            logger.error(f"❌ 文本生成失败: {str(e)}")
            
            return {
                "status": "error",
                "error": str(e),
                "content": ""
            }

    async def generate_with_messages(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tier: Literal["simple", "complex"] = "complex",
    ) -> Dict:
        """
        Chat completion with native message array (OpenAI-compatible format).

        Args:
            messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
            temperature: sampling temperature
            max_tokens: max tokens to generate
            tier: "simple" for QA/lookup (fast, cheap), "complex" for generation/review

        Returns:
            {"status": "success"|"error", "content": str}
        """
        start_time = time.time()

        # Select model by tier
        model = (
            settings.MODEL_TIER_SIMPLE if tier == "simple"
            else settings.MODEL_TIER_COMPLEX
        )

        try:
            response = await self._get_client(tier).chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={"enable_thinking": False},
            )

            content = response.choices[0].message.content.strip()
            # Expose finish_reason so callers can detect max_tokens truncation
            # (finish_reason == "length") — critical for large-output chapters
            # like G25a whose JSON silently breaks when truncated.
            finish_reason = getattr(response.choices[0], "finish_reason", None)

            duration_ms = (time.time() - start_time) * 1000
            log_api_call("通义千问LLM", "消息生成", "success", duration_ms)

            return {
                "status": "success",
                "content": content,
                "finish_reason": finish_reason,
            }

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("通义千问LLM", "消息生成", "error", duration_ms)
            logger.error(f"❌ 消息生成失败: {str(e)}")

            return {
                "status": "error",
                "error": str(e),
                "content": "",
                "finish_reason": None,
            }

    async def generate_with_messages_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tier: Literal["simple", "complex"] = "complex",
    ) -> AsyncGenerator[Dict[str, str], None]:
        """Streaming chat completion.

        Yields dicts with keys:
          - {"type": "thinking", "content": "..."} for model reasoning tokens
          - {"type": "content", "content": "..."} for regular output tokens
        """
        start_time = time.time()
        model = self._get_model(tier)
        client = self._get_client(tier)

        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                extra_body={"enable_thinking": True},
            )

            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if not choice:
                    continue

                delta = choice.delta

                # Reasoning/thinking tokens (supported by DeepSeek-R1 etc.)
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    yield {"type": "thinking", "content": reasoning}

                # Regular content tokens
                if delta.content:
                    yield {"type": "content", "content": delta.content}

                # If the stream is finished, break
                if choice.finish_reason:
                    break

            duration_ms = (time.time() - start_time) * 1000
            log_api_call("通义千问LLM", "流式消息生成", "success", duration_ms)

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("通义千问LLM", "流式消息生成", "error", duration_ms)
            logger.error(f"❌ 流式消息生成失败: {str(e)}")
            yield {"type": "error", "content": str(e)}

# 创建全局实例
llm_service = QwenLLMService()


def get_llm(tier: str = "complex"):
    """
    获取LangChain兼容的LLM实例
    用于Agent和风格学习等需要LangChain接口的场景

    Args:
        tier: "simple" or "complex" (default: complex)

    Returns:
        ChatOpenAI实例(兼容通义千问)
    """
    from langchain_openai import ChatOpenAI

    model = (
        settings.MODEL_TIER_SIMPLE if tier == "simple"
        else settings.MODEL_TIER_COMPLEX
    )
    base_url = (
        settings.DASHSCOPE_BASE_URL_SIMPLE if tier == "simple"
        else settings.DASHSCOPE_BASE_URL_COMPLEX
    ) or settings.DASHSCOPE_BASE_URL

    return ChatOpenAI(
        model=model,
        openai_api_key=settings.DASHSCOPE_API_KEY,
        openai_api_base=base_url,
        temperature=0.7,
        max_tokens=2000
    )
