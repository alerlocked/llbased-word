"""
视觉语言模型服务
使用 Qwen-VL-Max (DashScope) 进行所有图像处理任务：
- OCR文字识别
- 图表/插图提取
- 图片描述生成
- 图片内容理解
"""
import base64
import time
import json
import re
from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple
import dashscope
from dashscope import MultiModalConversation

from app.config import settings
from app.utils.logger import logger, log_api_call


class VLService:
    """视觉语言模型服务 (Qwen-VL 单引擎架构)"""
    
    def __init__(self):
        """
        初始化服务
        使用 Qwen-VL (DashScope) 处理所有视觉任务
        """
        dashscope.api_key = settings.DASHSCOPE_API_KEY
        self.qwen_model = settings.QWEN_VL_MODEL
        
    def _encode_image(self, image_path: Path) -> str:
        """
        将图片编码为 base64 字符串
        """
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
                return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            logger.error(f"❌ 图片编码失败: {str(e)}")
            raise
    
    async def generate_caption(self, image_path: Path) -> str:
        """
        [Qwen-VL] 为图片生成详细描述（用于检索）
        """
        start_time = time.time()
        try:
            logger.info(f"🖼️ [Qwen] 开始生成图片描述: {image_path.name}")
            image_base64 = self._encode_image(image_path)
            
            prompt = """请详细描述这张图片的内容，包括：
1. 图片中的主要对象和场景
2. 图片中的文字内容（如果有）
3. 图片的类型（如：图表、照片、示意图等）
4. 图片的关键信息和数据（如果是图表）
5. 图片的用途和上下文意义

请用中文输出，描述要详细且准确，便于后续检索和理解。"""
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"image": f"data:image/jpeg;base64,{image_base64}"},
                        {"text": prompt}
                    ]
                }
            ]
            
            response = MultiModalConversation.call(
                model=self.qwen_model,
                messages=messages
            )
            
            if response.status_code == 200:
                caption = response.output.choices[0].message.content[0].get("text", "")
                duration_ms = (time.time() - start_time) * 1000
                log_api_call("Qwen-VL", "生成图片描述", "success", duration_ms)
                return caption.strip()
            else:
                raise Exception(f"API调用失败: {response.message}")
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("Qwen-VL", "生成图片描述", "error", duration_ms)
            logger.error(f"❌ [Qwen] 图片描述生成失败: {str(e)}")
            return f"图片描述生成失败: {image_path.name}"
    
    async def ocr_page_to_markdown(self, image_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        """
        使用 Qwen-VL 进行全流程处理：OCR识别 + 图表提取
        """
        start_time = time.time()
        try:
            logger.info(f"📄 [OCR] 开始识别: {image_path.name}")
            
            # 阶段1：Qwen-VL 全文 OCR
            markdown_content = await self._qwen_ocr_page(image_path)
            markdown_content = self._clean_text(markdown_content)
            
            # 阶段2：Qwen-VL 图表提取
            figures = await self._extract_figures_with_qwen(image_path)
            
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("VLService", "OCR流程(Qwen单引擎)", "success", duration_ms)
            logger.info(f"✅ [OCR] 识别完成，正文长度={len(markdown_content)}，图表数={len(figures)}")
            
            return markdown_content.strip(), figures

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("VLService", "OCR流程", "error", duration_ms)
            logger.error(f"❌ [OCR] 识别失败: {str(e)}")
            raise

    async def _qwen_ocr_page(self, image_path: Path) -> str:
        """
        [Qwen-VL] 专门用于页面 OCR 的调用
        """
        start_time = time.time()
        try:
            image_base64 = self._encode_image(image_path)
            
            prompt = """请对这张图片进行高精度 OCR 文字识别：

1. 提取所有可见的文字内容
2. 保持原始的段落结构、标题层级
3. 如果有表格，转换为 Markdown 表格格式
4. 保持列表、引用等格式
5. 直接输出识别的文字，使用标准 Markdown 格式

请完整输出所有识别到的内容："""
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"image": f"data:image/jpeg;base64,{image_base64}"},
                        {"text": prompt}
                    ]
                }
            ]
            
            response = MultiModalConversation.call(
                model=self.qwen_model,
                messages=messages
            )
            
            if response.status_code == 200:
                content = response.output.choices[0].message.content[0].get("text", "")
                duration_ms = (time.time() - start_time) * 1000
                log_api_call("Qwen-VL", "页面OCR", "success", duration_ms)
                return content.strip()
            else:
                raise Exception(f"Qwen API调用失败: {response.message}")
        except Exception as e:
            logger.error(f"❌ [Qwen-OCR] 识别失败: {str(e)}")
            raise

    async def _extract_figures_with_qwen(self, image_path: Path) -> List[Dict[str, Any]]:
        """
        [Qwen-VL] 使用 Prompt 工程提取图表的结构化信息
        """
        start_time = time.time()
        try:
            image_base64 = self._encode_image(image_path)
            
            prompt = """请分析这张图片中的视觉元素（图表、插图、截图、照片等）：

1. 识别图片中包含的所有独立视觉元素。
2. 对每个元素，判断其类型（如：图表、插图、截图、照片）。
3. 生成简短标题 (caption) 和详细内容描述 (description)。
4. **请务必只输出合法的 JSON 字符串**，格式如下：

{
  "figures": [
    {
      "type": "chart/diagram/photo/screenshot",
      "caption": "图表标题",
      "description": "图表的详细描述，包含关键数据和趋势"
    }
  ]
}

如果图片中没有显著的独立图表或插图（仅为纯文本），请返回：
{"figures": []}

注意：不要使用 Markdown 代码块包裹 JSON，直接输出 JSON 字符串。"""
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"image": f"data:image/jpeg;base64,{image_base64}"},
                        {"text": prompt}
                    ]
                }
            ]
            
            response = MultiModalConversation.call(
                model=self.qwen_model,
                messages=messages
            )
            
            if response.status_code == 200:
                content = response.output.choices[0].message.content[0].get("text", "").strip()
                duration_ms = (time.time() - start_time) * 1000
                log_api_call("Qwen-VL", "图表提取", "success", duration_ms)
                
                # 解析 JSON
                figures = self._parse_figures_json(content)
                logger.info(f"📊 [Qwen] 提取到 {len(figures)} 个图表")
                return figures
            else:
                raise Exception(f"Qwen API调用失败: {response.message}")
                
        except Exception as e:
            logger.warning(f"⚠️ [Qwen] 图表提取失败: {str(e)}，不影响正文")
            return []

    def _parse_figures_json(self, content: str) -> List[Dict[str, Any]]:
        """
        解析 Qwen-VL 返回的图表 JSON
        """
        try:
            # 尝试直接解析
            data = json.loads(content)
            if isinstance(data, dict) and "figures" in data:
                return data["figures"] or []
            return []
        except json.JSONDecodeError:
            # 如果包含 Markdown 代码块，提取 JSON
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    if isinstance(data, dict) and "figures" in data:
                        return data["figures"] or []
                except json.JSONDecodeError:
                    pass
            
            # 尝试提取花括号内容
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                    if isinstance(data, dict) and "figures" in data:
                        return data["figures"] or []
                except json.JSONDecodeError:
                    pass
            
            logger.warning(f"⚠️ [Qwen] JSON 解析失败，内容: {content[:200]}")
            return []

    def _clean_text(self, text: str) -> str:
        """
        清洗文本：过滤非可打印字符，保留中文、英文、常见标点
        """
        cleaned = re.sub(
            r"[^\x09\x0A\x0D\x20-\x7E\u4e00-\u9fff。，、！？；：""''（）【】《》…—·]", 
            "", 
            text
        )
        return cleaned.strip()
    
    async def understand_image_content(self, image_path: Path, query: str) -> str:
        """
        [Qwen-VL] 理解图片内容并回答相关问题
        """
        start_time = time.time()
        
        try:
            logger.info(f"🔍 [Qwen] 开始理解图片内容: {image_path.name}")
            
            image_base64 = self._encode_image(image_path)
            
            prompt = f"问题：{query}\n\n请根据图片内容，提供详细、准确的回答。"
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"image": f"data:image/jpeg;base64,{image_base64}"},
                        {"text": prompt}
                    ]
                }
            ]
            
            response = MultiModalConversation.call(
                model=self.qwen_model,
                messages=messages
            )
            
            if response.status_code == 200:
                answer = response.output.choices[0].message.content[0].get("text", "")
                duration_ms = (time.time() - start_time) * 1000
                log_api_call("Qwen-VL", "图片理解", "success", duration_ms)
                return answer.strip()
            else:
                raise Exception(f"API调用失败: {response.message}")
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("Qwen-VL", "图片理解", "error", duration_ms)
            logger.error(f"❌ [Qwen] 图片理解失败: {str(e)}")
            raise


# 创建全局实例
vl_service = VLService()
