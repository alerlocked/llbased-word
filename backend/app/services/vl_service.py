"""
视觉语言模型服务
支持多后端架构：
- MinerU VLM (本地，5-10秒/页)
- Qwen-VL-Max (DashScope，云端，20-50秒/页)
"""
import base64
import time
import json
import re
import asyncio
from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple, Union
from concurrent.futures import ThreadPoolExecutor
import tempfile
import os
import shutil

from app.config import settings
from app.utils.logger import logger, log_api_call


class VLService:
    """
    视觉语言模型服务 - 多后端架构

    后端选择：
    - mineru: 使用 MinerU VLM（本地，5-10秒/页）
    - qwen: 使用 Qwen-VL API（云端，20-50秒/页）

    并行处理：
    - 支持 process_pages_parallel 方法
    - 默认 4 页并行处理
    """

    def __init__(self, backend: Optional[str] = None):
        """
        初始化服务

        Args:
            backend: 后端选择
                - "mineru": 使用 MinerU VLM（本地，5-10秒/页）
                - "qwen": 使用 Qwen-VL API（云端，20-50秒/页）
                - None: 使用配置文件中的默认后端
        """
        self.backend = backend or settings.VL_SERVICE_BACKEND
        self.max_workers = settings.VL_SERVICE_MAX_WORKERS
        self.fallback_to_qwen = settings.VL_SERVICE_FALLBACK_TO_QWEN

        # 初始化后端
        self._mineru_extractor = None
        self._qwen_initialized = False

        if self.backend == "mineru":
            self._init_mineru_backend()
        elif self.backend == "qwen":
            self._init_qwen_backend()
        else:
            logger.warning(f"vl_service_unknown_backend", backend=self.backend, fallback="qwen")
            self.backend = "qwen"
            self._init_qwen_backend()

        logger.info("vl_service_initialized",
                   backend=self.backend,
                   max_workers=self.max_workers,
                   fallback_enabled=self.fallback_to_qwen)

    def _init_mineru_backend(self):
        """初始化 MinerU 后端"""
        try:
            from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor
            self._mineru_extractor = MinerUTableExtractor({
                "mineru_config": {
                    "backend": settings.MINERU_BACKEND,
                    "table_model": settings.MINERU_TABLE_MODEL,
                    "lang": settings.MINERU_LANG,
                }
            })

            if not self._mineru_extractor.is_available():
                logger.warning("mineru_not_available", fallback_enabled=self.fallback_to_qwen)
                if self.fallback_to_qwen:
                    self.backend = "qwen"
                    self._init_qwen_backend()
                else:
                    logger.error("mineru_not_available_no_fallback")
            else:
                logger.info("mineru_backend_initialized",
                           backend_info=self._mineru_extractor.get_backend_info())

        except ImportError as e:
            logger.warning("mineru_import_failed", error=str(e), fallback_enabled=self.fallback_to_qwen)
            if self.fallback_to_qwen:
                self.backend = "qwen"
                self._init_qwen_backend()
            else:
                raise ImportError("MinerU未安装且未启用回退，请运行: pip install mineru[all]")

    def _init_qwen_backend(self):
        """初始化 Qwen-VL 后端"""
        try:
            import dashscope
            dashscope.api_key = settings.DASHSCOPE_API_KEY
            self.qwen_model = settings.QWEN_VL_MODEL
            self._qwen_initialized = True
            logger.info("qwen_backend_initialized", model=self.qwen_model)
        except ImportError:
            logger.error("dashscope_import_failed")
            raise ImportError("DashScope未安装，请运行: pip install dashscope")

    # ==================== 公共API ====================

    async def ocr_page_to_markdown(
        self,
        image_path: Path,
        backend: Optional[str] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        使用指定后端进行 OCR 识别

        Args:
            image_path: 图片路径
            backend: 临时覆盖后端（可选）

        Returns:
            (markdown_content, figures)
        """
        use_backend = backend or self.backend
        start_time = time.time()

        try:
            logger.info("ocr_page_started", image=image_path.name, backend=use_backend)

            if use_backend == "mineru":
                markdown_content, figures = await self._ocr_with_mineru(image_path)
            else:
                markdown_content, figures = await self._ocr_with_qwen(image_path)

            markdown_content = self._clean_text(markdown_content)

            duration_ms = (time.time() - start_time) * 1000
            log_api_call(f"VLService-{use_backend}", "OCR流程", "success", duration_ms)
            logger.info("ocr_page_completed",
                       image=image_path.name,
                       content_length=len(markdown_content),
                       figures_count=len(figures),
                       duration_ms=duration_ms)

            return markdown_content.strip(), figures

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call(f"VLService-{use_backend}", "OCR流程", "error", duration_ms)
            logger.error("ocr_page_failed", image=image_path.name, error=str(e))

            # 如果 MinerU 失败且启用了回退
            if use_backend == "mineru" and self.fallback_to_qwen:
                logger.info("ocr_fallback_to_qwen", image=image_path.name)
                return await self._ocr_with_qwen(image_path)

            raise

    async def process_pages_parallel(
        self,
        image_paths: List[Path],
        max_workers: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        并行处理多页

        Args:
            image_paths: 图片路径列表
            max_workers: 最大并行数（默认使用配置值）

        Returns:
            处理结果列表，每个元素包含:
            - success: bool
            - markdown: str (成功时)
            - figures: List[Dict] (成功时)
            - error: str (失败时)
            - image_path: str
        """
        workers = max_workers or self.max_workers
        total = len(image_paths)
        start_time = time.time()

        logger.info("parallel_processing_started",
                   total_pages=total,
                   max_workers=workers,
                   backend=self.backend)

        results = []

        # 分批并行处理
        for batch_start in range(0, total, workers):
            batch_end = min(batch_start + workers, total)
            batch = image_paths[batch_start:batch_end]

            logger.debug("processing_batch",
                        batch_start=batch_start,
                        batch_end=batch_end,
                        batch_size=len(batch))

            # 并行处理当前批次
            tasks = [self._process_single_page(path) for path in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理结果
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    results.append({
                        "success": False,
                        "error": str(result),
                        "image_path": str(batch[i])
                    })
                else:
                    results.append(result)

            # 进度日志
            completed = batch_end
            progress_pct = (completed / total) * 100
            logger.info("parallel_processing_progress",
                       completed=completed,
                       total=total,
                       progress_pct=f"{progress_pct:.1f}%")

        # 统计结果
        success_count = sum(1 for r in results if r.get("success", False))
        duration_ms = (time.time() - start_time) * 1000
        avg_time_per_page = duration_ms / total if total > 0 else 0

        logger.info("parallel_processing_completed",
                   total_pages=total,
                   success_count=success_count,
                   failed_count=total - success_count,
                   duration_ms=duration_ms,
                   avg_time_per_page_ms=avg_time_per_page)

        return results

    async def _process_single_page(self, image_path: Path) -> Dict[str, Any]:
        """处理单个页面"""
        try:
            markdown, figures = await self.ocr_page_to_markdown(image_path)
            return {
                "success": True,
                "markdown": markdown,
                "figures": figures,
                "image_path": str(image_path)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "image_path": str(image_path)
            }

    # ==================== MinerU 后端 ====================

    async def _ocr_with_mineru(self, image_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        """
        使用 MinerU VLM 进行 OCR
        """
        start_time = time.time()

        if not self._mineru_extractor or not self._mineru_extractor.is_available():
            raise RuntimeError("MinerU 后端不可用")

        try:
            logger.debug("mineru_ocr_started", image=image_path.name)

            # MinerU 处理 PDF，需要先将图片转换为 PDF 或使用其他方式
            # 这里使用 MinerU 的图像处理能力
            markdown_content = await self._mineru_image_to_markdown(image_path)
            figures = await self._extract_figures_with_mineru(image_path)

            duration_ms = (time.time() - start_time) * 1000
            log_api_call("MinerU", "OCR", "success", duration_ms)

            return markdown_content, figures

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("MinerU", "OCR", "error", duration_ms)
            logger.error("mineru_ocr_failed", image=image_path.name, error=str(e))
            raise

    async def _mineru_image_to_markdown(self, image_path: Path) -> str:
        """
        使用 MinerU 处理图片并转换为 Markdown
        """
        loop = asyncio.get_event_loop()

        with ThreadPoolExecutor(max_workers=1) as executor:
            result = await loop.run_in_executor(
                executor,
                self._mineru_image_to_markdown_sync,
                image_path
            )

        return result

    def _mineru_image_to_markdown_sync(self, image_path: Path) -> str:
        """
        同步执行 MinerU 图像处理
        """
        import img2pdf
        from mineru.cli.common import do_parse

        temp_dir = None
        temp_pdf_path = None

        try:
            # 将图片转换为 PDF（MinerU 需要 PDF 输入）
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                temp_pdf_path = f.name

            with open(temp_pdf_path, 'wb') as f:
                with open(image_path, 'rb') as img_f:
                    pdf_bytes = img2pdf.convert(img_f.read())
                    f.write(pdf_bytes)

            # 创建临时输出目录
            temp_dir = tempfile.mkdtemp(prefix="mineru_ocr_")
            output_dir = os.path.join(temp_dir, "output")

            # 执行 MinerU 解析
            pdf_filename = os.path.basename(temp_pdf_path)
            with open(temp_pdf_path, 'rb') as f:
                pdf_bytes = f.read()

            do_parse(
                output_dir=output_dir,
                pdf_file_names=[pdf_filename],
                pdf_bytes_list=[pdf_bytes],
                p_lang_list=[settings.MINERU_LANG],
                backend=settings.MINERU_BACKEND,
                parse_method="auto",
                formula_enable=False,
                table_enable=True,
                f_draw_layout_bbox=False,
                f_draw_span_bbox=False,
                f_dump_md=True,
                f_dump_middle_json=False,
                f_dump_model_output=False,
                f_dump_orig_pdf=False,
                f_dump_content_list=False,
            )

            # 读取 Markdown 输出
            md_content = ""
            for root, dirs, files in os.walk(output_dir):
                for f in files:
                    if f.endswith('.md'):
                        md_path = os.path.join(root, f)
                        with open(md_path, 'r', encoding='utf-8') as mf:
                            md_content = mf.read()
                        break

            return md_content

        except ImportError:
            logger.warning("img2pdf_not_available", fallback="qwen")
            raise RuntimeError("img2pdf 未安装，无法使用 MinerU 处理图片")
        finally:
            # 清理临时文件
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                try:
                    os.unlink(temp_pdf_path)
                except Exception:
                    pass
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass

    async def _extract_figures_with_mineru(self, image_path: Path) -> List[Dict[str, Any]]:
        """
        使用 MinerU 提取图表信息
        """
        # MinerU 在解析过程中已经提取了图表，这里返回空列表
        # 如果需要单独提取图表，可以调用 Qwen 的图表提取功能
        return []

    # ==================== Qwen-VL 后端 ====================

    def _ensure_qwen_ready(self):
        """确保 Qwen 后端已初始化"""
        if not self._qwen_initialized:
            self._init_qwen_backend()

    async def _ocr_with_qwen(self, image_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        """
        使用 Qwen-VL 进行 OCR + 图表提取
        """
        self._ensure_qwen_ready()

        start_time = time.time()
        try:
            logger.debug("qwen_ocr_started", image=image_path.name)

            # 阶段1：Qwen-VL 全文 OCR
            markdown_content = await self._qwen_ocr_page(image_path)

            # 阶段2：Qwen-VL 图表提取
            figures = await self._extract_figures_with_qwen(image_path)

            duration_ms = (time.time() - start_time) * 1000
            log_api_call("Qwen-VL", "OCR流程", "success", duration_ms)

            return markdown_content, figures

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("Qwen-VL", "OCR流程", "error", duration_ms)
            logger.error("qwen_ocr_failed", image=image_path.name, error=str(e))
            raise

    def _encode_image(self, image_path: Path) -> str:
        """将图片编码为 base64 字符串"""
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
                return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            logger.error("image_encoding_failed", error=str(e))
            raise

    async def _qwen_ocr_page(self, image_path: Path) -> str:
        """Qwen-VL 页面 OCR"""
        from dashscope import MultiModalConversation

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
            logger.error("qwen_ocr_failed", image=image_path.name, error=str(e))
            raise

    async def _extract_figures_with_qwen(self, image_path: Path) -> List[Dict[str, Any]]:
        """Qwen-VL 图表提取"""
        from dashscope import MultiModalConversation

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

                figures = self._parse_figures_json(content)
                logger.debug("qwen_figures_extracted", count=len(figures))
                return figures
            else:
                raise Exception(f"Qwen API调用失败: {response.message}")

        except Exception as e:
            logger.warning("qwen_figure_extraction_failed", error=str(e))
            return []

    def _parse_figures_json(self, content: str) -> List[Dict[str, Any]]:
        """解析 Qwen-VL 返回的图表 JSON"""
        try:
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

            logger.warning("json_parse_failed", content_preview=content[:200])
            return []

    def _clean_text(self, text: str) -> str:
        """清洗文本：过滤非可打印字符，保留中文、英文、常见标点"""
        cleaned = re.sub(
            r"[^\x09\x0A\x0D\x20-\x7E\u4e00-\u9fff。，、！？；：""''（）【】《》…—·]",
            "",
            text
        )
        return cleaned.strip()

    # ==================== 其他功能 ====================

    async def generate_caption(self, image_path: Path) -> str:
        """为图片生成详细描述（用于检索）- 使用 Qwen 后端"""
        from dashscope import MultiModalConversation

        self._ensure_qwen_ready()
        start_time = time.time()

        try:
            logger.debug("caption_generation_started", image=image_path.name)
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
            logger.error("caption_generation_failed", error=str(e))
            return f"图片描述生成失败: {image_path.name}"

    async def understand_image_content(self, image_path: Path, query: str) -> str:
        """理解图片内容并回答相关问题 - 使用 Qwen 后端"""
        from dashscope import MultiModalConversation

        self._ensure_qwen_ready()
        start_time = time.time()

        try:
            logger.debug("image_understanding_started", image=image_path.name)
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
            logger.error("image_understanding_failed", error=str(e))
            raise

    def get_backend_info(self) -> Dict[str, Any]:
        """获取当前后端信息"""
        info = {
            "current_backend": self.backend,
            "max_workers": self.max_workers,
            "fallback_to_qwen": self.fallback_to_qwen,
            "available_backends": ["qwen"],
        }

        if self._mineru_extractor and self._mineru_extractor.is_available():
            info["available_backends"].insert(0, "mineru")
            info["mineru_info"] = self._mineru_extractor.get_backend_info()

        info["qwen_info"] = {
            "model": getattr(self, 'qwen_model', 'qwen-vl-max'),
            "initialized": self._qwen_initialized
        }

        return info


# 创建全局实例
vl_service = VLService()
