"""
DeepSeek API服务
使用OpenAI兼容格式调用DeepSeek API
"""
import time
import json
from typing import List, Dict, Optional, AsyncGenerator, Literal
from openai import OpenAI, AsyncOpenAI

from app.config import settings
from app.utils.logger import logger


class DeepSeekService:
    """DeepSeek文本生成服务"""

    def __init__(self):
        """
        初始化DeepSeek客户端
        使用OpenAI兼容格式调用
        """
        self.api_key = settings.DEEPSEEK_API_KEY
        self.base_url = settings.DEEPSEEK_BASE_URL
        self.model = settings.DEEPSEEK_MODEL

        if not self.api_key or self.api_key == "your-deepseek-api-key-here":
            logger.warning("DeepSeek API Key not configured, service will not be available")
            self._client = None
            self._async_client = None
        else:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            self._async_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            logger.info("DeepSeek service initialized", model=self.model)

    @property
    def is_available(self) -> bool:
        """检查服务是否可用"""
        return self._client is not None

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False
    ) -> Dict:
        """
        聊天补全接口

        Args:
            messages: 消息列表 [{"role": "user/assistant/system", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大token数
            stream: 是否流式输出

        Returns:
            包含status和content的字典
        """
        if not self.is_available:
            return {
                "status": "error",
                "error": "DeepSeek API Key not configured",
                "content": ""
            }

        start_time = time.time()

        try:
            response = await self._async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )

            if stream:
                # 流式响应返回生成器
                return {
                    "status": "success",
                    "stream": response
                }

            content = response.choices[0].message.content.strip()

            duration_ms = (time.time() - start_time) * 1000
            logger.info("deepseek_chat_completed", duration_ms=duration_ms, tokens=response.usage.total_tokens if response.usage else 0)

            return {
                "status": "success",
                "content": content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                }
            }

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error("deepseek_chat_failed", error=str(e), duration_ms=duration_ms)
            return {
                "status": "error",
                "error": str(e),
                "content": ""
            }

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """
        流式聊天补全

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数

        Yields:
            增量文本内容
        """
        if not self.is_available:
            yield "[ERROR] DeepSeek API Key not configured"
            return

        try:
            stream = await self._async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error("deepseek_stream_failed", error=str(e))
            yield f"[ERROR] {str(e)}"

    async def generate_process_document(
        self,
        intent: str,
        context: Dict,
        style: str = "standard"
    ) -> Dict:
        """
        生成工艺文档内容

        Args:
            intent: 工艺意图描述
            context: 上下文信息（包含已有内容、标准库信息等）
            style: 文档风格 (standard/detailed/concise)

        Returns:
            生成的文档内容
        """
        style_prompts = {
            "standard": "使用标准工艺文件格式，语言规范严谨",
            "detailed": "使用详细工艺文件格式，包含更多操作细节和注意事项",
            "concise": "使用简洁工艺文件格式，重点突出关键步骤"
        }

        system_prompt = f"""你是一位专业的工艺文件编写助手，擅长将工艺师的意图转化为符合标准的工艺文件术语。
请根据用户的工艺意图，结合上下文信息，生成规范的工艺文件内容。

写作要求：
1. {style_prompts.get(style, style_prompts['standard'])}
2. 使用行业标准的工艺术语
3. 确保内容准确、完整、规范
4. 按照工艺文件的格式要求组织内容"""

        user_prompt = f"""请根据以下信息生成工艺文件内容：

【工艺意图】
{intent}

【上下文信息】
{json.dumps(context, ensure_ascii=False, indent=2) if context else '无'}

请生成工艺文件内容："""

        return await self.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,
            max_tokens=3000
        )

    async def align_terminology(
        self,
        text: str,
        terminology_db: List[Dict]
    ) -> Dict:
        """
        术语对齐：将文本中的非标准术语转换为标准工艺术语

        Args:
            text: 原始文本
            terminology_db: 术语库列表

        Returns:
            对齐后的文本和修改说明
        """
        system_prompt = """你是一位工艺术语专家，负责将文本中的非标准术语转换为标准工艺术语。
请检查文本中的术语，并将其替换为标准术语。"""

        user_prompt = f"""请检查以下文本，将其中的非标准术语替换为标准工艺术语：

【原始文本】
{text}

【标准术语库】
{json.dumps(terminology_db, ensure_ascii=False, indent=2)}

请输出：
1. 修正后的文本
2. 修改说明（列出所有替换的术语）"""

        result = await self.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=3000
        )

        return result

    async def check_compliance(
        self,
        document: str,
        rules: List[str]
    ) -> Dict:
        """
        合规检查：检查工艺文档是否符合规范

        Args:
            document: 工艺文档内容
            rules: 合规规则列表

        Returns:
            检查结果和修改建议
        """
        system_prompt = """你是一位工艺文件审核专家，负责检查工艺文档是否符合企业规范和行业标准。
请仔细检查文档内容，指出不符合规范的地方，并给出修改建议。"""

        user_prompt = f"""请检查以下工艺文档是否符合规范：

【工艺文档】
{document}

【合规规则】
{chr(10).join(f'- {rule}' for rule in rules)}

请输出：
1. 合规检查结果（通过/不通过）
2. 不符合规范的具体问题
3. 修改建议"""

        result = await self.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=3000
        )

        return result


# 创建全局实例
deepseek_service = DeepSeekService()


def get_deepseek_service() -> DeepSeekService:
    """获取DeepSeek服务实例"""
    return deepseek_service
