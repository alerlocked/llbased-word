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
        
    def check_llm_reachable(self, timeout: float = 5.0) -> tuple[bool, str]:
        """Probe LLM server reachability via GET /models.

        Sync (blocking) — callers MUST run via asyncio.to_thread to avoid
        blocking the event loop. Mirrors main.py _check_model_server LLM probe.
        Returns (True, "") if reachable, else (False, reason).
        """
        import urllib.request
        import urllib.error
        llm_url = settings.DASHSCOPE_BASE_URL_COMPLEX or self._default_base_url
        try:
            req = urllib.request.Request(f"{llm_url.rstrip('/')}/models", method="GET")
            if self.api_key:
                req.add_header("Authorization", f"Bearer {self.api_key}")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return True, ""
                return False, f"HTTP {resp.status}"
        except urllib.error.URLError as e:
            return False, f"连接失败: {e.reason}"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

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

        # Route through the resilience wrapper (retry/backoff/trim), adapting
        # the non-stream path via a single-message collect through the same
        # stream transport for consistent error handling.
        result = await self._generate_with_retry(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            tier=tier,
            model=model,
            start_time=start_time,
        )
        if "finish_reason" in result:
            # generate_text contract is {"status","content"[,"error"]} — keep it
            return {k: v for k, v in result.items() if k != "finish_reason"}
        return result

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

        return await self._generate_with_retry(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tier=tier,
            model=model,
            start_time=start_time,
        )

    async def _generate_with_retry(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        tier: str,
        model: str,
        start_time: float,
        max_retries: int = 2,
    ) -> Dict:
        """Resilience wrapper around _collect_stream_content.

        1 initial call + up to `max_retries` retries with exponential backoff.
        Per-class mitigation (llm_errors): transient classes retry; CONTEXT_OVERFLOW
        applies one context trim then retries; EMPTY_REPLY retries with the same
        messages. Error dicts gain an additive "error_class" key; the four
        contract keys {"status","content","finish_reason","error"} are untouched.
        """
        from app.services.llm_errors import (
            LLMErrorClass,
            classify_exception,
            should_retry,
            trim_messages_for_overflow,
            USER_FACING_MESSAGES,
        )

        import asyncio as _asyncio

        current_messages = messages
        trimmed = False  # context trim applied at most once
        attempt = 0
        while True:
            try:
                # Stream mode (was non-stream + fallback): qwen3 enable_thinking
                # requires stream call (400 "enable_thinking only support stream
                # call" on non-stream). _collect_stream_content streams with
                # enable_thinking+thinking_budget, collects delta.content (discards
                # reasoning_content). Returns (content, finish_reason).
                content, finish_reason = await self._collect_stream_content(
                    messages=current_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tier=tier,
                )
                if not content:
                    # EMPTY_REPLY: retry with the same messages before failing
                    error_class = LLMErrorClass.EMPTY_REPLY
                    if should_retry(error_class, attempt, max_retries):
                        delay = 0.5 * (2 ** attempt)
                        logger.warning(
                            "llm_call_retry",
                            attempt=attempt + 1, error_class=error_class.value,
                            delay_s=delay, model=model,
                        )
                        await _asyncio.sleep(delay)
                        attempt += 1
                        continue
                    duration_ms = (time.time() - start_time) * 1000
                    log_api_call("通义千问LLM", "消息生成", "error", duration_ms)
                    logger.error(
                        "llm_empty_content_stream",
                        model=model, finish_reason=finish_reason,
                    )
                    return {
                        "status": "error",
                        "error": USER_FACING_MESSAGES[error_class],
                        "error_class": error_class.value,
                        "content": "",
                        "finish_reason": finish_reason,
                    }

                duration_ms = (time.time() - start_time) * 1000
                log_api_call("通义千问LLM", "消息生成", "success", duration_ms)

                return {
                    "status": "success",
                    "content": content,
                    "finish_reason": finish_reason,
                }

            except Exception as e:
                error_class = classify_exception(e)
                # CONTEXT_OVERFLOW: trim once (the mitigation), then keep retrying
                # within the normal budget — the trimmed payload may still be
                # near the limit and succeed on a retry.
                if (
                    error_class == LLMErrorClass.CONTEXT_OVERFLOW
                    and not trimmed
                    and any(m.get("role") == "user" for m in current_messages)
                ):
                    current_messages = trim_messages_for_overflow(current_messages)
                    trimmed = True
                    logger.warning(
                        "llm_call_retry",
                        attempt=attempt + 1, error_class=error_class.value,
                        delay_s=0.0, model=model, trimmed=True,
                    )
                    attempt += 1
                    continue
                if error_class == LLMErrorClass.CONTEXT_OVERFLOW or should_retry(
                    error_class, attempt, max_retries
                ):
                    if attempt >= max_retries:
                        # budget exhausted
                        duration_ms = (time.time() - start_time) * 1000
                        log_api_call("通义千问LLM", "消息生成", "error", duration_ms)
                        logger.error(
                            "llm_call_failed",
                            error_class=error_class.value, model=model, error=str(e),
                        )
                        return {
                            "status": "error",
                            "error": f"{USER_FACING_MESSAGES[error_class]}（{e}）",
                            "error_class": error_class.value,
                            "content": "",
                            "finish_reason": None,
                        }
                    delay = 1.0 * (2 ** attempt)
                    logger.warning(
                        "llm_call_retry",
                        attempt=attempt + 1, error_class=error_class.value,
                        delay_s=delay, model=model,
                    )
                    await _asyncio.sleep(delay)
                    attempt += 1
                    continue
                duration_ms = (time.time() - start_time) * 1000
                log_api_call("通义千问LLM", "消息生成", "error", duration_ms)
                logger.error(
                    "llm_call_failed",
                    error_class=error_class.value, model=model, error=str(e),
                )
                return {
                    "status": "error",
                    "error": f"{USER_FACING_MESSAGES[error_class]}（{e}）",
                    "error_class": error_class.value,
                    "content": "",
                    "finish_reason": None,
                }

    async def _collect_stream_content(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        tier: str,
    ) -> tuple:
        """Collect the full content via streaming (empty-content fallback).

        Reasoning models reliably emit the final answer as delta.content when
        streaming with enable_thinking=True; reasoning_content (chain-of-thought)
        is discarded. Returns (content, finish_reason).
        """
        content_parts: List[str] = []
        finish_reason = None
        stream = await self._get_client(tier).chat.completions.create(
            model=self._get_model(tier),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            extra_body={"enable_thinking": True, "thinking_budget": 1024},
        )
        async for chunk in stream:
            choice = chunk.choices[0] if chunk.choices else None
            if not choice:
                continue
            delta = choice.delta
            if delta.content:
                content_parts.append(delta.content)
            if choice.finish_reason:
                finish_reason = choice.finish_reason
                break
        return "".join(content_parts).strip(), finish_reason

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
                extra_body={"enable_thinking": True, "thinking_budget": 1024},
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
            from app.services.llm_errors import classify_exception, USER_FACING_MESSAGES
            error_class = classify_exception(e)
            logger.error(
                "llm_stream_failed",
                error_class=error_class.value, model=model, error=str(e),
            )
            yield {
                "type": "error",
                "content": f"{USER_FACING_MESSAGES[error_class]}（{e}）",
                "error_class": error_class.value,
            }

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
