"""
视觉语言模型服务
支持多后端架构：
- MinerU VLM (本地，5-10秒/页)
- Qwen-VL-Max (DashScope，云端，20-50秒/页)
- Qwen2.5-VL Local (MindIE on 300I Duo, OpenAI-compatible, 3-8秒/页)
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

import httpx

from app.config import settings
from app.shared.logging import get_logger
logger = get_logger(__name__)
from app.shared.logging import log_api_call


class VLService:
    """
    视觉语言模型服务 - 多后端架构

    后端选择：
    - mineru: 使用 MinerU VLM（本地，5-10秒/页）
    - qwen: 使用 Qwen-VL API（云端，20-50秒/页）
    - qwen_local: 使用 Qwen2.5-VL on MindIE（300I Duo NPU，3-8秒/页）

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
                - "qwen_local": 使用 Qwen2.5-VL on MindIE（300I Duo NPU，3-8秒/页）
                - None: 使用配置文件中的默认后端
        """
        self.backend = backend or settings.VL_SERVICE_BACKEND
        self.max_workers = settings.VL_SERVICE_MAX_WORKERS
        self.fallback_to_qwen = settings.VL_SERVICE_FALLBACK_TO_QWEN

        # Local VLM config
        self._vl_local_url = settings.VL_LOCAL_BASE_URL
        self._vl_local_model = settings.VL_LOCAL_MODEL

        # 初始化后端
        self._mineru_extractor = None
        self._qwen_initialized = False
        # MinerU loads a 6GB model — defer to first OCR (lazy) so uvicorn
        # hot-reload no longer reloads the model on every code change.
        # qwen/qwen_local are lightweight (cloud API / HTTP), keep eager.
        self._mineru_predictor = None
        self._mineru_lock = asyncio.Lock()

        if self.backend == "mineru":
            pass  # lazy: _ensure_mineru_ready() loads on first OCR
        elif self.backend == "qwen":
            self._init_qwen_backend()
        elif self.backend == "qwen_local":
            self._init_qwen_local_backend()
        else:
            logger.warning(f"vl_service_unknown_backend", backend=self.backend, fallback="qwen")
            self.backend = "qwen"
            self._init_qwen_backend()

        logger.info("vl_service_initialized",
                   backend=self.backend,
                   max_workers=self.max_workers,
                   fallback_enabled=self.fallback_to_qwen)

    def _init_mineru_backend(self):
        """初始化 MinerU VLM 后端"""
        try:
            from mineru.backend.vlm.vlm_analyze import ModelSingleton

            # Resolve server_url for http-client backend (NPU VLM)
            server_url = settings.MINERU_VL_SERVER or None
            if settings.MINERU_BACKEND == "http-client" and not server_url:
                raise ValueError(
                    "MINERU_BACKEND=http-client requires MINERU_VL_SERVER "
                    "(e.g. http://192.168.13.153:1040/v1)"
                )

            # 获取 MinerU VLM predictor
            self._mineru_predictor = ModelSingleton().get_model(
                backend=settings.MINERU_BACKEND,
                model_path=None,
                server_url=server_url
            )

            logger.info("mineru_vlm_backend_initialized",
                       backend=settings.MINERU_BACKEND,
                       server_url=server_url,
                       predictor_type=type(self._mineru_predictor).__name__)

        except ImportError as e:
            logger.warning("mineru_import_failed", error=str(e), fallback_enabled=self.fallback_to_qwen)
            if self.fallback_to_qwen:
                self.backend = "qwen"
                self._init_qwen_backend()
            else:
                raise ImportError("MinerU未安装且未启用回退，请运行: pip install mineru[all]")
        except Exception as e:
            logger.error("mineru_init_failed", error=str(e), fallback_enabled=self.fallback_to_qwen)
            if self.fallback_to_qwen:
                self.backend = "qwen"
                self._init_qwen_backend()
            else:
                raise

    async def _ensure_mineru_ready(self):
        """Lazy-load MinerU predictor on first OCR.

        Lock guards against concurrent first-load races; the ~30s sync model
        load runs off the event loop. Replaces eager loading in __init__ so
        uvicorn hot-reload no longer reloads the 6GB model on every code change
        — only the first OCR after a reload pays the load, then it stays resident.
        """
        if self._mineru_predictor is not None:
            return
        async with self._mineru_lock:
            if self._mineru_predictor is not None:
                return
            await asyncio.to_thread(self._init_mineru_backend)

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

    def _init_qwen_local_backend(self):
        """初始化 Qwen2.5-VL 本地后端 (MindIE on 300I Duo)"""
        logger.info("qwen_local_backend_initialized",
                    url=self._vl_local_url,
                    model=self._vl_local_model)

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
            elif use_backend == "qwen_local":
                markdown_content, figures = await self._ocr_with_qwen_local(image_path)
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
        使用 MinerU VLM 进行 OCR（正确方式）
        使用 two_step_extract 直接处理图片，无需 img2pdf 转换
        """
        await self._ensure_mineru_ready()
        if not self._mineru_predictor:
            # _init_mineru_backend fell back to qwen — route there
            return await self._ocr_with_qwen(image_path)

        start_time = time.time()

        try:
            logger.debug("mineru_ocr_started", image=image_path.name)

            # 加载图片
            from PIL import Image
            image_pil = Image.open(image_path).convert("RGB")

            # 使用 MinerU VLM 处理图片（正确 API）
            markdown_content = await self._mineru_image_to_markdown(image_path, image_pil)

            # 提取图表信息（从 content_blocks 中提取）
            # 注意：这里需要在同步方法中提取，但我们已经在前面的方法中处理了
            # 暂时返回空列表，后续可以优化
            figures = []

            duration_ms = (time.time() - start_time) * 1000
            log_api_call("MinerU-VLM", "OCR", "success", duration_ms)

            return markdown_content, figures

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("MinerU-VLM", "OCR", "error", duration_ms)
            logger.error("mineru_vlm_ocr_failed", image=image_path.name, error=str(e))
            raise

    async def ocr_pages_batch_mineru(
        self,
        image_paths: List[Path],
    ) -> List[Tuple[str, List[Dict[str, Any]]]]:
        """
        Batch-OCR multiple pages in one call (mineru 3.4 transformers backend).

        Uses predictor.batch_two_step_extract, which runs a single model.generate
        over multiple images per batch_size — true batch, no thread-safety race,
        faster than per-page serial two_step_extract. Returned list order aligns
        with image_paths.

        Returns:
            list of (markdown_content, figures) aligned with image_paths.
            figures kept empty [] to match current single-page behavior.
        """
        await self._ensure_mineru_ready()
        if not self._mineru_predictor:
            raise RuntimeError("MinerU VLM 后端不可用（lazy 加载失败；document_processor 会回退逐页串行）")

        from PIL import Image

        start_time = time.time()
        logger.info("mineru_batch_started", pages=len(image_paths))

        try:
            images_pil = [Image.open(p).convert("RGB") for p in image_paths]

            # True batch inference (sync) — run off the event loop
            extract_results = await asyncio.to_thread(
                self._mineru_predictor.batch_two_step_extract,
                images_pil,
            )

            results: List[Tuple[str, List[Dict[str, Any]]]] = []
            for path, extract_result in zip(image_paths, extract_results):
                if not extract_result:
                    logger.warning("mineru_batch_empty_page", image=path.name)
                    results.append(("", []))
                    continue
                markdown_content = self._content_blocks_to_markdown(extract_result)
                markdown_content = self._clean_text(markdown_content)
                # figures kept empty to match current single-page behavior
                results.append((markdown_content.strip(), []))

            duration_ms = (time.time() - start_time) * 1000
            log_api_call("MinerU-VLM", "batch_ocr", "success", duration_ms)
            logger.info("mineru_batch_completed",
                        pages=len(image_paths), duration_ms=duration_ms)
            return results

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("MinerU-VLM", "batch_ocr", "error", duration_ms)
            logger.error("mineru_batch_failed", pages=len(image_paths), error=str(e))
            raise

    async def _mineru_image_to_markdown(self, image_path: Path, image_pil) -> str:
        """
        使用 MinerU VLM 处理图片并转换为 Markdown
        使用 two_step_extract 方法（正确的 VLM API）
        """
        loop = asyncio.get_event_loop()

        with ThreadPoolExecutor(max_workers=1) as executor:
            result = await loop.run_in_executor(
                executor,
                self._mineru_image_to_markdown_sync,
                image_pil
            )

        return result

    def _mineru_image_to_markdown_sync(self, image_pil) -> str:
        """
        同步执行 MinerU VLM 图像处理
        使用 two_step_extract 方法（单张图片的正确 API）
        """
        try:
            # 使用 MinerU VLM 的 two_step_extract 方法（单张图片）
            content_blocks = self._mineru_predictor.two_step_extract(image_pil)

            if not content_blocks:
                logger.warning("mineru_vlm_empty_result")
                return ""

            # 将 ContentBlock 列表转换为 markdown
            return self._content_blocks_to_markdown(content_blocks)

        except Exception as e:
            logger.error("mineru_vlm_processing_failed", error=str(e))
            raise

    def _content_blocks_to_markdown(self, content_blocks: list) -> str:
        """
        将 MinerU ContentBlock 列表转换为 Markdown

        Args:
            content_blocks: MinerU VLM 返回的内容块列表

        Returns:
            Markdown 文本
        """
        md_parts = []

        for block in content_blocks:
            block_type = block.type
            content = block.content or ""
            bbox = getattr(block, 'bbox', None)

            if block_type == "title":
                # 标题
                md_parts.append(f"\n# {content}\n")

            elif block_type in ["text", "list"]:
                # 普通文本
                md_parts.append(f"\n{content}\n")

            elif block_type == "table":
                # 表格（content 已是 HTML 格式）
                md_parts.append(f"\n{content}\n")

            elif block_type == "equation":
                # 公式
                md_parts.append(f"\n$$\n{content}\n$$\n")

            elif block_type in ["code", "algorithm"]:
                # 代码块
                md_parts.append(f"\n```\n{content}\n```\n")

            elif block_type == "image":
                # 图片标记
                bbox_str = str(bbox) if bbox else "未知位置"
                md_parts.append(f"\n[图片: {bbox_str}]\n")

            elif block_type in ["image_caption", "table_caption"]:
                # 标题/说明
                md_parts.append(f"\n{content}\n")

            else:
                # 未知类型，作为文本处理
                if content.strip():
                    md_parts.append(f"\n{content}\n")

        return "\n".join(md_parts)

    def _extract_figures_from_blocks(self, content_blocks: list) -> List[Dict[str, Any]]:
        """
        从 ContentBlock 中提取图表信息

        Args:
            content_blocks: MinerU VLM 返回的内容块列表

        Returns:
            图表信息列表
        """
        figures = []

        for block in content_blocks:
            if block.type == "table":
                figures.append({
                    "type": "table",
                    "caption": "",
                    "description": block.content or "",
                    "bbox": getattr(block, 'bbox', None),
                })

            elif block.type == "image":
                figures.append({
                    "type": "image",
                    "caption": "",
                    "description": "",
                    "bbox": getattr(block, 'bbox', None),
                })

        return figures

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

    # ==================== Qwen Local (MindIE) Backend ====================

    async def _ocr_with_qwen_local(self, image_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        """
        使用 Qwen2.5-VL on MindIE (300I Duo) 进行 OCR + 图表提取
        Uses OpenAI-compatible API exposed by MindIE.
        """
        start_time = time.time()
        try:
            logger.debug("qwen_local_ocr_started", image=image_path.name)

            # Step 1: OCR full page
            markdown_content = await self._qwen_local_ocr_page(image_path)

            # Step 2: Extract figures
            figures = await self._extract_figures_with_qwen_local(image_path)

            duration_ms = (time.time() - start_time) * 1000
            log_api_call("Qwen-Local-VL", "OCR流程", "success", duration_ms)

            return markdown_content, figures

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("Qwen-Local-VL", "OCR流程", "error", duration_ms)
            logger.error("qwen_local_ocr_failed", image=image_path.name, error=str(e))
            raise

    async def _qwen_local_call(self, image_base64: str, prompt: str) -> str:
        """Call Qwen2.5-VL via MindIE OpenAI-compatible API."""
        url = f"{self._vl_local_url}/chat/completions"
        payload = {
            "model": self._vl_local_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                        },
                        {"type": "text", "text": prompt}
                    ]
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.1
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"]

    async def _qwen_local_ocr_page(self, image_path: Path) -> str:
        """Qwen2.5-VL page OCR via MindIE"""
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

            content = await self._qwen_local_call(image_base64, prompt)
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("Qwen-Local-VL", "页面OCR", "success", duration_ms)
            return content.strip()

        except Exception as e:
            logger.error("qwen_local_page_ocr_failed", image=image_path.name, error=str(e))
            raise

    async def _extract_figures_with_qwen_local(self, image_path: Path) -> List[Dict[str, Any]]:
        """Qwen2.5-VL figure extraction via MindIE"""
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

            content = await self._qwen_local_call(image_base64, prompt)
            duration_ms = (time.time() - start_time) * 1000
            log_api_call("Qwen-Local-VL", "图表提取", "success", duration_ms)

            figures = self._parse_figures_json(content)
            logger.debug("qwen_local_figures_extracted", count=len(figures))
            return figures

        except Exception as e:
            logger.warning("qwen_local_figure_extraction_failed", error=str(e))
            return []

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

        if hasattr(self, '_mineru_predictor') and self._mineru_predictor:
            info["available_backends"].insert(0, "mineru")
            info["mineru_info"] = {
                "type": "vlm",
                "backend": settings.MINERU_BACKEND,
                "initialized": True,
                "predictor_type": type(self._mineru_predictor).__name__
            }

        info["qwen_info"] = {
            "model": getattr(self, 'qwen_model', 'qwen-vl-max'),
            "initialized": self._qwen_initialized
        }

        return info


# 创建全局实例
vl_service = VLService()
