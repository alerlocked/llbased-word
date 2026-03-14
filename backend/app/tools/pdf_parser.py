"""
工艺文件辅助编辑系统 - PDF解析工具

双复杂度模式：
- 简单模式 (SIMPLE): 无表格，使用PyMuPDF快速解析
- 复杂模式 (COMPLEX): 有表格，使用MinerU-VLM高精度解析
"""
import fitz  # PyMuPDF
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import hashlib
import tempfile
import os

from app.tools.parser_selector import ParserSelector
from app.models.table_models import ParserType
from app.shared.logging import get_logger

logger = get_logger(__name__)


class PDFParser:
    """
    PDF解析工具 - 双复杂度模式

    根据文档是否有表格自动选择解析模式：
    - 简单模式: PyMuPDF快速解析文本和图像
    - 复杂模式: MinerU-VLM高精度解析表格和结构
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化PDF解析器

        Args:
            config: 配置参数
                - force_mode: 强制模式 ("simple" | "complex" | None)
                - enable_caching: 是否启用缓存
                - image_extraction_enabled: 是否提取图像
        """
        self.config = config or {}
        self.force_mode = self.config.get("force_mode", None)
        self.enable_caching = self.config.get("enable_caching", True)
        self.image_extraction_enabled = self.config.get("image_extraction_enabled", False)

        # 初始化解析器选择器
        self._selector = ParserSelector(self.config)

        # 检查MinerU可用性
        self._mineru_available = self._check_mineru_available()

        # 初始化缓存
        if self.enable_caching:
            self._cache = {}
            self._cache_size_limit = 100

        logger.info("pdf_parser_initialized",
                   force_mode=self.force_mode,
                   caching_enabled=self.enable_caching,
                   mineru_available=self._mineru_available)

    async def parse(
        self,
        pdf_source: Union[str, bytes],
        extract_tables: bool = True,
        extract_text: bool = True,
        extract_images: bool = False,
        identify_structure: bool = True,
        force_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        解析PDF文档

        Args:
            pdf_source: PDF文件路径或二进制数据
            extract_tables: 是否提取表格
            extract_text: 是否提取文本
            extract_images: 是否提取图像
            identify_structure: 是否识别文档结构
            force_mode: 强制模式 ("simple" | "complex" | None)

        Returns:
            解析结果，包含:
            - pages: 页面数据
            - tables: 表格数据（仅复杂模式）
            - document_info: 文档信息
            - metadata: 解析元数据
        """
        try:
            # 1. 选择解析模式
            mode = force_mode or self.force_mode
            selection = await self._selector.select_parser(pdf_source, mode)

            # 2. 检查缓存
            cache_key = None
            if self.enable_caching:
                cache_key = self._get_cache_key(pdf_source)
                cached_result = self._get_from_cache(cache_key)
                if cached_result is not None:
                    logger.info("cache_hit", cache_key=cache_key)
                    return cached_result

            # 3. 根据模式选择解析方法
            if selection.selected_parser == ParserType.COMPLEX and self._mineru_available:
                logger.info("using_complex_mode", table_count=selection.table_count)
                result = await self._parse_complex(pdf_source, extract_tables, extract_text)
            else:
                logger.info("using_simple_mode", has_tables=selection.has_tables)
                result = await self._parse_simple(pdf_source, extract_text, extract_images)

            # 4. 添加元数据
            result["metadata"] = {
                "parser_mode": selection.selected_parser.value,
                "parser_used": "mineru-vlm" if selection.selected_parser == ParserType.COMPLEX else "pymupdf",
                "has_tables": selection.has_tables,
                "table_count": selection.table_count if selection.has_tables else 0,
                "selection_reasoning": selection.reasoning
            }

            # 5. 识别文档结构（可选）
            if identify_structure and "pages" in result:
                result["structure"] = await self._identify_document_structure(result["pages"])

            # 6. 保存到缓存
            if self.enable_caching and cache_key:
                self._save_to_cache(cache_key, result)

            logger.info("pdf_parsed",
                       parser_mode=result["metadata"]["parser_mode"],
                       total_pages=len(result.get("pages", [])),
                       tables_extracted=len(result.get("tables", [])))

            return result

        except Exception as e:
            logger.error("pdf_parsing_error", error=str(e))
            raise e

    # ============ 简单模式 (PyMuPDF) ============

    async def _parse_simple(
        self,
        pdf_source: Union[str, bytes],
        extract_text: bool = True,
        extract_images: bool = False
    ) -> Dict[str, Any]:
        """
        简单模式解析 - 使用PyMuPDF快速解析

        Args:
            pdf_source: PDF源
            extract_text: 是否提取文本
            extract_images: 是否提取图像

        Returns:
            解析结果
        """
        doc = None
        try:
            # 加载PDF
            doc = await self._load_pdf_document(pdf_source)
            if not doc:
                raise ValueError("无法加载PDF文档")

            # 获取文档信息
            doc_info = await self._get_document_info(doc)

            # 解析所有页面
            pages = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_data = await self._parse_page_simple(page, page_num, extract_text, extract_images)
                pages.append(page_data)

            return {
                "pages": pages,
                "document_info": doc_info,
                "tables": []  # 简单模式不提取表格
            }

        finally:
            if doc:
                doc.close()

    async def _parse_page_simple(
        self,
        page: fitz.Page,
        page_num: int,
        extract_text: bool,
        extract_images: bool
    ) -> Dict[str, Any]:
        """
        简单模式解析单个页面

        Args:
            page: PyMuPDF页面对象
            page_num: 页码
            extract_text: 是否提取文本
            extract_images: 是否提取图像

        Returns:
            页面数据
        """
        page_data = {
            "page_number": page_num,
            "width": page.rect.width,
            "height": page.rect.height,
            "rotation": page.rotation
        }

        # 提取文本
        if extract_text:
            text_blocks = await self._extract_text_blocks(page)
            page_data["text_blocks"] = text_blocks
            page_data["full_text"] = "\n".join([block["text"] for block in text_blocks])

        # 提取图像
        if extract_images and self.image_extraction_enabled:
            image_blocks = await self._extract_image_blocks(page)
            page_data["image_blocks"] = image_blocks

        return page_data

    async def _extract_text_blocks(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """提取文本块"""
        try:
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
            text_blocks = []

            for block in blocks:
                if "lines" in block:
                    block_text = ""
                    for line in block["lines"]:
                        line_text = ""
                        for span in line["spans"]:
                            line_text += span["text"]
                        block_text += line_text + "\n"

                    text_blocks.append({
                        "bbox": block["bbox"],
                        "text": block_text.strip(),
                        "block_type": "text",
                        "confidence": 1.0
                    })

            return text_blocks

        except Exception as e:
            logger.warning("text_extraction_failed", error=str(e), page_number=page.number)
            return []

    async def _extract_image_blocks(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """提取图像块"""
        try:
            image_list = page.get_images()
            image_blocks = []

            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = page.parent.extract_image(xref)

                image_blocks.append({
                    "index": img_index,
                    "width": base_image["width"],
                    "height": base_image["height"],
                    "format": base_image["ext"],
                    "xref": xref
                })

            return image_blocks

        except Exception as e:
            logger.warning("image_extraction_failed", error=str(e))
            return []

    # ============ 复杂模式 (MinerU-VLM) ============

    async def _parse_complex(
        self,
        pdf_source: Union[str, bytes],
        extract_tables: bool = True,
        extract_text: bool = True
    ) -> Dict[str, Any]:
        """
        复杂模式解析 - 使用MinerU-VLM高精度解析

        Args:
            pdf_source: PDF源
            extract_tables: 是否提取表格
            extract_text: 是否提取文本

        Returns:
            解析结果
        """
        try:
            from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor

            # 准备PDF路径
            temp_pdf_path = None
            if isinstance(pdf_source, bytes):
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                    f.write(pdf_source)
                    temp_pdf_path = f.name
                pdf_path = temp_pdf_path
            else:
                pdf_path = str(pdf_source)

            # 创建MinerU提取器
            extractor = MinerUTableExtractor({
                "mineru_config": {
                    "backend": "vlm-auto-engine",  # 使用VLM高精度模式
                    "table_enable": True,
                    "lang": "ch"
                }
            })

            # 提取表格
            tables = []
            if extract_tables:
                extracted_tables = await extractor.extract_tables(pdf_path)
                tables = [t.to_dict() if hasattr(t, 'to_dict') else t for t in extracted_tables]

            # 使用PyMuPDF提取文本（MinerU主要用于表格）
            pages = []
            doc_info = {}

            if extract_text:
                doc = await self._load_pdf_document(pdf_source)
                if doc:
                    doc_info = await self._get_document_info(doc)
                    for page_num in range(len(doc)):
                        page = doc[page_num]
                        page_data = await self._parse_page_simple(page, page_num, True, False)
                        pages.append(page_data)
                    doc.close()

            # 清理临时文件
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                try:
                    os.unlink(temp_pdf_path)
                except Exception:
                    pass

            return {
                "pages": pages,
                "tables": tables,
                "document_info": doc_info
            }

        except ImportError:
            logger.warning("mineru_not_available_fallback_to_simple")
            return await self._parse_simple(pdf_source, extract_text, False)
        except Exception as e:
            logger.error("complex_parsing_failed", error=str(e))
            # 回退到简单模式
            return await self._parse_simple(pdf_source, extract_text, False)

    # ============ 辅助方法 ============

    async def _load_pdf_document(self, pdf_source: Union[str, bytes]) -> Optional[fitz.Document]:
        """加载PDF文档"""
        try:
            if isinstance(pdf_source, str):
                if not Path(pdf_source).exists():
                    raise FileNotFoundError(f"PDF文件不存在: {pdf_source}")
                doc = fitz.open(pdf_source)
            elif isinstance(pdf_source, bytes):
                doc = fitz.open(stream=pdf_source, filetype="pdf")
            else:
                raise ValueError(f"不支持的PDF源类型: {type(pdf_source)}")

            if doc.is_encrypted:
                try:
                    doc.authenticate("")
                except Exception:
                    raise ValueError("无法打开加密的PDF文件")

            return doc

        except Exception as e:
            logger.error("failed_to_load_pdf", error=str(e))
            raise e

    async def _get_document_info(self, doc: fitz.Document) -> Dict[str, Any]:
        """获取文档基本信息"""
        try:
            info = doc.metadata
            return {
                "title": info.get("title", ""),
                "author": info.get("author", ""),
                "subject": info.get("subject", ""),
                "keywords": info.get("keywords", ""),
                "creator": info.get("creator", ""),
                "producer": info.get("producer", ""),
                "creation_date": info.get("creationDate", ""),
                "modification_date": info.get("modDate", ""),
                "page_count": len(doc),
                "is_encrypted": doc.is_encrypted
            }
        except Exception as e:
            logger.warning("failed_to_get_document_info", error=str(e))
            return {"page_count": len(doc)}

    async def _identify_document_structure(self, pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """识别文档结构"""
        try:
            return {
                "document_type": "process_document",
                "sections": [],
                "has_header": False,
                "has_footer": False,
                "has_tables": any("tables" in page for page in pages),
                "has_images": any("images" in page for page in pages)
            }
        except Exception as e:
            logger.warning("structure_identification_failed", error=str(e))
            return {"document_type": "unknown"}

    def _check_mineru_available(self) -> bool:
        """检查MinerU是否可用"""
        try:
            from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor
            extractor = MinerUTableExtractor()
            return extractor.is_available()
        except ImportError:
            return False
        except Exception:
            return False

    # ============ 缓存方法 ============

    def _get_cache_key(self, pdf_source: Union[str, bytes]) -> str:
        """生成缓存键"""
        if isinstance(pdf_source, str):
            file_path = Path(pdf_source)
            if file_path.exists():
                mtime = file_path.stat().st_mtime
                return f"{pdf_source}:{mtime}"
            return pdf_source
        else:
            return hashlib.md5(pdf_source).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """从缓存获取结果"""
        if not self.enable_caching or cache_key not in self._cache:
            return None
        return self._cache[cache_key]

    def _save_to_cache(self, cache_key: str, result: Dict[str, Any]) -> None:
        """保存结果到缓存"""
        if not self.enable_caching:
            return

        if len(self._cache) >= self._cache_size_limit:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[cache_key] = result

    # ============ 向后兼容方法 ============

    def _should_use_mineru(self) -> bool:
        """判断是否应该使用MinerU（向后兼容）"""
        return self._mineru_available

    async def validate_pdf_format(self, pdf_source: Union[str, bytes]) -> bool:
        """验证PDF格式"""
        try:
            doc = await self._load_pdf_document(pdf_source)
            if doc:
                doc.close()
                return True
            return False
        except Exception:
            return False
