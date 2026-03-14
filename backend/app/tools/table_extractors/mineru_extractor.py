"""
MinerU表格提取器 - 基于MinerU TableFormer的高精度表格提取

MinerU是开源的PDF解析工具，使用TableFormer模型实现高精度表格结构识别，
特别擅长处理合并单元格、跨页表格、复杂布局等场景。

安装方式：
    pip install mineru  # 基础安装
    pip install mineru[all]  # 完整安装（含VLM加速）

MinerU 2.7.6+ API使用：
    - pipeline后端：通用PDF解析，支持CPU/GPU
    - vlm后端：高精度VLM模型，需要GPU
    - hybrid后端：混合模式，结合pipeline和VLM优势
"""
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
import tempfile
import os
import json
import shutil

from app.tools.table_extractors.base_extractor import BaseTableExtractor
from app.models.table_models import ExtractedTable, TableMetadata, ParserType, TableType
from app.shared.logging import get_logger

logger = get_logger(__name__)

# 尝试导入MinerU配置，如果失败则使用默认值
try:
    from app.shared.config import MINERU_CONFIG
except ImportError:
    MINERU_CONFIG = {
        "enabled": True,
        "backend": "pipeline",  # pipeline / vlm-auto-engine / hybrid-auto-engine
        "table_model": "rapid_table",
        "enable_table_merge": True,
        "fallback_to_pdfplumber": True,
        "timeout_seconds": 300,
        "complexity_threshold": 0.8,
        "lang": "ch",  # 默认中文
    }


class MinerUTableExtractor(BaseTableExtractor):
    """
    MinerU表格提取器

    使用MinerU的TableFormer模型实现高精度表格提取，
    特别擅长处理合并单元格、跨页表格等复杂场景。

    特性：
    - 基于Vision Transformer的TableFormer模型
    - 支持合并单元格识别
    - 支持跨页表格合并
    - 优雅降级到pdfplumber

    MinerU 2.7.6+ 后端选项：
    - pipeline: 通用解析，支持CPU/GPU
    - vlm-auto-engine: 高精度VLM，需要GPU
    - hybrid-auto-engine: 混合模式，最佳精度
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化MinerU表格提取器

        Args:
            config: 配置参数，可覆盖默认的MINERU_CONFIG
        """
        super().__init__(config)

        # 合并配置
        self.mineru_config = {**MINERU_CONFIG, **self.config.get("mineru_config", {})}

        # 检查MinerU是否可用
        self._mineru_available = self._check_mineru_available()

        if not self._mineru_available:
            logger.warning("mineru_not_available",
                          fallback=self.mineru_config.get("fallback_to_pdfplumber", True))

        logger.info("mineru_extractor_initialized",
                   available=self._mineru_available,
                   backend=self.mineru_config.get("backend", "pipeline"),
                   fallback_enabled=self.mineru_config.get("fallback_to_pdfplumber", True))

    def _check_mineru_available(self) -> bool:
        """
        检查MinerU库是否可用

        Returns:
            MinerU是否可用
        """
        try:
            import mineru
            # 检查关键模块是否可用
            from mineru.cli.common import do_parse
            logger.debug("mineru_import_success",
                        version=getattr(mineru, '__version__', 'unknown'))
            return True
        except ImportError as e:
            logger.debug("mineru_import_failed", error=str(e))
            return False
        except Exception as e:
            logger.debug("mineru_check_failed", error=str(e))
            return False

    async def extract_tables(
        self,
        pdf_source: Union[str, bytes, Path],
        **kwargs
    ) -> List[ExtractedTable]:
        """
        从PDF中提取表格

        Args:
            pdf_source: PDF文件路径或二进制数据
            **kwargs: 额外参数
                - pages: 指定页码列表
                - force_mineru: 强制使用MinerU（即使不可用也报错而非回退）
                - backend: 覆盖配置中的backend
                - lang: 覆盖配置中的语言

        Returns:
            提取的表格列表
        """
        # 检查是否启用
        if not self.mineru_config.get("enabled", True):
            logger.info("mineru_disabled_by_config")
            return await self._fallback_extract(pdf_source, **kwargs)

        # 检查可用性
        if not self._mineru_available:
            if kwargs.get("force_mineru", False):
                raise ImportError("MinerU未安装，请运行: pip install mineru[all]")

            if self.mineru_config.get("fallback_to_pdfplumber", True):
                logger.info("mineru_not_available_fallback")
                return await self._fallback_extract(pdf_source, **kwargs)

            raise ImportError("MinerU未安装且未启用回退")

        try:
            logger.info("mineru_extraction_started",
                       source_type=type(pdf_source).__name__)

            # MinerU处理在线程池中执行（避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                tables = await loop.run_in_executor(
                    executor,
                    self._extract_tables_sync,
                    pdf_source,
                    kwargs
                )

            logger.info("mineru_extraction_completed",
                       table_count=len(tables))

            return tables

        except Exception as e:
            logger.error("mineru_extraction_failed", error=str(e))

            if self.mineru_config.get("fallback_to_pdfplumber", True):
                logger.info("falling_back_to_pdfplumber", reason=str(e))
                return await self._fallback_extract(pdf_source, **kwargs)

            raise

    def _extract_tables_sync(
        self,
        pdf_source: Union[str, bytes, Path],
        kwargs: Dict[str, Any]
    ) -> List[ExtractedTable]:
        """
        同步执行MinerU提取

        Args:
            pdf_source: PDF源
            kwargs: 额外参数

        Returns:
            提取的表格列表
        """
        temp_dir = None
        temp_pdf_path = None

        try:
            # 准备PDF文件路径
            if isinstance(pdf_source, bytes):
                # 写入临时文件
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                    f.write(pdf_source)
                    temp_pdf_path = f.name
                pdf_path = temp_pdf_path
            else:
                pdf_path = str(pdf_source)

            # 创建临时输出目录
            temp_dir = tempfile.mkdtemp(prefix="mineru_output_")
            output_dir = os.path.join(temp_dir, "output")

            logger.debug("mineru_parsing_started",
                        pdf_path=pdf_path,
                        output_dir=output_dir)

            # 获取配置
            backend = kwargs.get("backend", self.mineru_config.get("backend", "pipeline"))
            lang = kwargs.get("lang", self.mineru_config.get("lang", "ch"))
            parse_method = "auto"  # auto / txt / ocr

            # 执行MinerU解析
            self._run_mineru_parse(
                pdf_path=pdf_path,
                output_dir=output_dir,
                backend=backend,
                lang=lang,
                parse_method=parse_method
            )

            # 从输出中提取表格
            tables = self._extract_tables_from_output(output_dir, pdf_path)

            logger.info("mineru_tables_extracted",
                       total_tables=len(tables))

            return tables

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

    def _run_mineru_parse(
        self,
        pdf_path: str,
        output_dir: str,
        backend: str,
        lang: str,
        parse_method: str = "auto"
    ) -> None:
        """
        运行MinerU解析

        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            backend: 解析后端
            lang: 语言
            parse_method: 解析方法
        """
        from mineru.cli.common import do_parse

        # 读取PDF文件
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()

        # 获取文件名
        pdf_filename = os.path.basename(pdf_path)

        # 执行解析
        do_parse(
            output_dir=output_dir,
            pdf_file_names=[pdf_filename],
            pdf_bytes_list=[pdf_bytes],
            p_lang_list=[lang],
            backend=backend,
            parse_method=parse_method,
            formula_enable=False,  # 不需要公式识别
            table_enable=True,     # 启用表格识别
            f_draw_layout_bbox=False,
            f_draw_span_bbox=False,
            f_dump_md=True,        # 输出Markdown
            f_dump_middle_json=True,  # 输出中间JSON
            f_dump_model_output=False,
            f_dump_orig_pdf=False,
            f_dump_content_list=True,  # 输出内容列表
        )

        logger.debug("mineru_parse_completed",
                    output_dir=output_dir)

    def _extract_tables_from_output(
        self,
        output_dir: str,
        pdf_path: str
    ) -> List[ExtractedTable]:
        """
        从MinerU输出中提取表格

        Args:
            output_dir: 输出目录
            pdf_path: 原始PDF路径

        Returns:
            提取的表格列表
        """
        tables = []

        # 查找输出目录中的内容
        pdf_filename = os.path.basename(pdf_path)
        pdf_name = os.path.splitext(pdf_filename)[0]

        # MinerU输出目录结构: output_dir/{pdf_name}/{method}/
        # 查找实际的输出目录
        content_list_path = None
        middle_json_path = None

        for root, dirs, files in os.walk(output_dir):
            for f in files:
                if f == "content_list.json":
                    content_list_path = os.path.join(root, f)
                elif f == "middle.json":
                    middle_json_path = os.path.join(root, f)

        # 优先从 middle.json 提取表格（更完整的信息）
        if middle_json_path and os.path.exists(middle_json_path):
            tables = self._extract_from_middle_json(middle_json_path)
            if tables:
                return tables

        # 从 content_list.json 提取表格
        if content_list_path and os.path.exists(content_list_path):
            tables = self._extract_from_content_list(content_list_path)
            if tables:
                return tables

        # 从 Markdown 文件提取表格
        for root, dirs, files in os.walk(output_dir):
            for f in files:
                if f.endswith('.md'):
                    md_path = os.path.join(root, f)
                    md_tables = self._extract_from_markdown(md_path)
                    tables.extend(md_tables)

        return tables

    def _extract_from_middle_json(self, json_path: str) -> List[ExtractedTable]:
        """
        从middle.json提取表格

        Args:
            json_path: JSON文件路径

        Returns:
            表格列表
        """
        tables = []

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            pdf_info = data.get("pdf_info", [])
            table_idx = 0

            for page_idx, page_info in enumerate(pdf_info):
                # 获取预处理的块
                preproc_blocks = page_info.get("preproc_blocks", [])

                for block in preproc_blocks:
                    if block.get("type") == "table":
                        try:
                            table = self._convert_middle_json_table(
                                block,
                                table_idx,
                                page_idx
                            )
                            if table:
                                tables.append(table)
                                table_idx += 1
                        except Exception as e:
                            logger.warning("table_conversion_failed",
                                          table_index=table_idx,
                                          error=str(e))
                            continue

            logger.debug("extracted_from_middle_json",
                        table_count=len(tables))

        except Exception as e:
            logger.error("middle_json_parse_failed", error=str(e))

        return tables

    def _convert_middle_json_table(
        self,
        table_block: Dict[str, Any],
        index: int,
        page_number: int
    ) -> Optional[ExtractedTable]:
        """
        将middle.json中的表格块转换为ExtractedTable

        Args:
            table_block: 表格块数据
            index: 表格索引
            page_number: 页码

        Returns:
            ExtractedTable实例
        """
        try:
            # 获取表格的HTML内容
            html_content = None

            # 尝试从blocks中获取HTML
            blocks = table_block.get("blocks", [])
            for block in blocks:
                if block.get("type") == "table_body":
                    # 查找lines中的html内容
                    lines = block.get("lines", [])
                    for line in lines:
                        spans = line.get("spans", [])
                        for span in spans:
                            if "html" in span:
                                html_content = span["html"]
                                break
                            if "content" in span and "<table" in str(span.get("content", "")):
                                html_content = span["content"]
                                break

            # 尝试直接获取html属性
            if not html_content:
                html_content = table_block.get("html")

            # 尝试从text中提取（可能包含HTML）
            if not html_content:
                text = table_block.get("text", "")
                if "<table" in text:
                    html_content = text

            if not html_content:
                logger.warning("no_html_in_middle_json", table_index=index)
                return None

            # 解析HTML提取单元格数据
            rows = self._parse_html_table(html_content)

            if not rows:
                logger.warning("no_rows_from_middle_json", table_index=index)
                return None

            # 检测合并单元格
            has_merged = self._detect_merged_from_html(html_content)

            # 获取边界框
            bbox = table_block.get("bbox", (0, 0, 0, 0))
            if isinstance(bbox, list):
                bbox = tuple(bbox)

            # 创建元数据
            metadata = TableMetadata(
                has_merged_cells=has_merged,
                is_continuation=table_block.get("is_continuation", False),
                continuation_of=table_block.get("continuation_of"),
                has_border=True,
                confidence_score=0.95,
                extraction_method="mineru_tableformer"
            )

            # 检测表格类型
            table_type_str = self._detect_table_type(rows[0] if rows else None)
            table_type = TableType(table_type_str)

            return ExtractedTable(
                table_id=f"mineru_p{page_number}_{index}",
                page_number=page_number,
                bbox=bbox,
                rows=rows,
                columns=len(rows[0]) if rows else 0,
                confidence_score=0.95,
                extraction_method="mineru",
                parser_used=ParserType.MINERU,
                metadata=metadata,
                table_type=table_type
            )

        except Exception as e:
            logger.error("convert_middle_json_table_failed",
                        error=str(e),
                        table_index=index)
            return None

    def _extract_from_content_list(self, json_path: str) -> List[ExtractedTable]:
        """
        从content_list.json提取表格

        Args:
            json_path: JSON文件路径

        Returns:
            表格列表
        """
        tables = []

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                content_list = json.load(f)

            table_idx = 0
            current_page = 0

            for item in content_list:
                # 更新页码
                if "page_idx" in item:
                    current_page = item["page_idx"]

                # 检查是否是表格类型
                if item.get("type") == "table":
                    try:
                        table = self._convert_content_list_table(
                            item,
                            table_idx,
                            current_page
                        )
                        if table:
                            tables.append(table)
                            table_idx += 1
                    except Exception as e:
                        logger.warning("content_list_table_conversion_failed",
                                      table_index=table_idx,
                                      error=str(e))
                        continue

            logger.debug("extracted_from_content_list",
                        table_count=len(tables))

        except Exception as e:
            logger.error("content_list_parse_failed", error=str(e))

        return tables

    def _convert_content_list_table(
        self,
        table_item: Dict[str, Any],
        index: int,
        page_number: int
    ) -> Optional[ExtractedTable]:
        """
        将content_list中的表格项转换为ExtractedTable

        Args:
            table_item: 表格项数据
            index: 表格索引
            page_number: 页码

        Returns:
            ExtractedTable实例
        """
        try:
            # 获取表格内容
            # content_list中的表格通常有text或html字段
            html_content = table_item.get("html") or table_item.get("text")

            if not html_content:
                # 尝试从img_path获取（图片表格）
                img_path = table_item.get("img_path")
                if img_path:
                    logger.debug("table_is_image", table_index=index)
                    return None
                return None

            # 如果内容不是HTML表格，尝试解析
            if "<table" not in str(html_content).lower():
                logger.debug("no_table_tag_in_content", table_index=index)
                return None

            # 解析HTML
            rows = self._parse_html_table(str(html_content))

            if not rows:
                return None

            # 检测合并单元格
            has_merged = self._detect_merged_from_html(str(html_content))

            # 获取边界框
            bbox = table_item.get("bbox", (0, 0, 0, 0))
            if isinstance(bbox, list):
                bbox = tuple(bbox)

            # 创建元数据
            metadata = TableMetadata(
                has_merged_cells=has_merged,
                is_continuation=False,
                has_border=True,
                confidence_score=0.90,
                extraction_method="mineru_content_list"
            )

            # 检测表格类型
            table_type_str = self._detect_table_type(rows[0] if rows else None)
            table_type = TableType(table_type_str)

            return ExtractedTable(
                table_id=f"mineru_p{page_number}_{index}",
                page_number=page_number,
                bbox=bbox,
                rows=rows,
                columns=len(rows[0]) if rows else 0,
                confidence_score=0.90,
                extraction_method="mineru",
                parser_used=ParserType.MINERU,
                metadata=metadata,
                table_type=table_type
            )

        except Exception as e:
            logger.error("convert_content_list_table_failed",
                        error=str(e),
                        table_index=index)
            return None

    def _extract_from_markdown(self, md_path: str) -> List[ExtractedTable]:
        """
        从Markdown文件提取表格

        Args:
            md_path: Markdown文件路径

        Returns:
            表格列表
        """
        tables = []

        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析Markdown表格
            md_tables = self._parse_markdown_tables(content)

            for idx, rows in enumerate(md_tables):
                if not rows:
                    continue

                try:
                    metadata = TableMetadata(
                        has_merged_cells=False,
                        has_border=True,
                        confidence_score=0.85,
                        extraction_method="mineru_markdown"
                    )

                    table_type_str = self._detect_table_type(rows[0])
                    table_type = TableType(table_type_str)

                    table = ExtractedTable(
                        table_id=f"mineru_md_{idx}",
                        page_number=0,  # Markdown没有页码信息
                        bbox=(0, 0, 0, 0),
                        rows=rows,
                        columns=len(rows[0]) if rows else 0,
                        confidence_score=0.85,
                        extraction_method="mineru",
                        parser_used=ParserType.MINERU,
                        metadata=metadata,
                        table_type=table_type
                    )
                    tables.append(table)

                except Exception as e:
                    logger.warning("markdown_table_conversion_failed",
                                  table_index=idx,
                                  error=str(e))
                    continue

            logger.debug("extracted_from_markdown",
                        table_count=len(tables))

        except Exception as e:
            logger.error("markdown_parse_failed", error=str(e))

        return tables

    def _parse_markdown_tables(self, content: str) -> List[List[List[str]]]:
        """
        解析Markdown中的表格

        Args:
            content: Markdown内容

        Returns:
            表格列表，每个表格是二维数组
        """
        tables = []
        lines = content.split('\n')
        current_table = []
        in_table = False

        for line in lines:
            # 检测表格行（以|开头和结尾）
            if line.strip().startswith('|') and line.strip().endswith('|'):
                if not in_table:
                    in_table = True
                    current_table = []

                # 解析行
                cells = [cell.strip() for cell in line.strip()[1:-1].split('|')]

                # 跳过分隔行（如 |---|---|）
                if all(set(c) <= set('-:|') for c in cells):
                    continue

                current_table.append(cells)

            else:
                # 表格结束
                if in_table and current_table:
                    tables.append(current_table)
                    current_table = []
                in_table = False

        # 处理最后一个表格
        if current_table:
            tables.append(current_table)

        return tables

    def _parse_html_table(self, html: str) -> List[List[str]]:
        """
        解析HTML表格为二维数组，正确处理colspan和rowspan

        MinerU生成的HTML包含colspan/rowspan属性，需要特殊处理：
        - colspan: 单元格跨多列，内容需要填充到多个列位置
        - rowspan: 单元格跨多行，内容需要填充到下面多行的对应位置

        Args:
            html: HTML表格内容

        Returns:
            二维数组，每行是一个字符串列表
        """
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table')

            if not table:
                return []

            # 第一步：收集所有行和单元格信息
            tr_list = table.find_all('tr')
            if not tr_list:
                return []

            # 第二步：计算表格的总列数
            max_cols = 0
            for tr in tr_list:
                col_count = 0
                for cell in tr.find_all(['td', 'th']):
                    colspan = int(cell.get('colspan', 1))
                    col_count += colspan
                max_cols = max(max_cols, col_count)

            if max_cols == 0:
                return []

            # 第三步：使用占用矩阵处理合并单元格
            # occupied[row][col] = True 表示该位置已被合并单元格占用
            num_rows = len(tr_list)
            occupied = [[False] * max_cols for _ in range(num_rows)]
            result = [[''] * max_cols for _ in range(num_rows)]

            for row_idx, tr in enumerate(tr_list):
                col_idx = 0
                cells = tr.find_all(['td', 'th'])

                for cell in cells:
                    # 找到下一个未被占用的列位置
                    while col_idx < max_cols and occupied[row_idx][col_idx]:
                        col_idx += 1

                    if col_idx >= max_cols:
                        break

                    # 获取单元格属性
                    colspan = int(cell.get('colspan', 1))
                    rowspan = int(cell.get('rowspan', 1))
                    text = cell.get_text(strip=True)

                    # 填充单元格内容到所有跨度的位置
                    for r in range(row_idx, min(row_idx + rowspan, num_rows)):
                        for c in range(col_idx, min(col_idx + colspan, max_cols)):
                            # 只在第一个位置填入内容，其他位置标记为占用
                            if r == row_idx and c == col_idx:
                                result[r][c] = text
                            else:
                                # 合并区域内的其他单元格，可以选择填入相同内容或留空
                                # 这里选择填入内容，便于后续处理
                                result[r][c] = text
                                occupied[r][c] = True

                    # 标记当前行的占用情况（rowspan>1时）
                    if rowspan > 1:
                        for r in range(row_idx + 1, min(row_idx + rowspan, num_rows)):
                            for c in range(col_idx, min(col_idx + colspan, max_cols)):
                                occupied[r][c] = True

                    col_idx += colspan

            return result

        except ImportError:
            logger.warning("beautifulsoup_not_available")
            return self._parse_html_simple(html)
        except Exception as e:
            logger.warning("html_parse_failed", error=str(e))
            return self._parse_html_simple(html)

    def _parse_html_simple(self, html: str) -> List[List[str]]:
        """
        简单的HTML表格解析（不依赖BeautifulSoup）

        Args:
            html: HTML表格内容

        Returns:
            二维数组
        """
        import re

        rows = []
        # 查找所有行
        tr_pattern = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
        cell_pattern = re.compile(r'<t[dh][^>]*>(.*?)</t[dh]>', re.DOTALL | re.IGNORECASE)
        clean_pattern = re.compile(r'<[^>]+>')

        for tr_match in tr_pattern.finditer(html):
            tr_content = tr_match.group(1)
            cells = []
            for cell_match in cell_pattern.finditer(tr_content):
                cell_content = cell_match.group(1)
                # 移除内部标签
                clean_text = clean_pattern.sub('', cell_content).strip()
                cells.append(clean_text)
            if cells:
                rows.append(cells)

        return rows

    def _detect_merged_from_html(self, html: str) -> bool:
        """
        从HTML检测合并单元格

        Args:
            html: HTML内容

        Returns:
            是否有合并单元格
        """
        import re
        # 检查colspan或rowspan属性
        return bool(re.search(r'colspan\s*=\s*["\']?\d', html, re.IGNORECASE)) or \
               bool(re.search(r'rowspan\s*=\s*["\']?\d', html, re.IGNORECASE))

    async def _fallback_extract(
        self,
        pdf_source: Union[str, bytes, Path],
        **kwargs
    ) -> List[ExtractedTable]:
        """
        回退到pdfplumber提取

        Args:
            pdf_source: PDF源
            **kwargs: 额外参数

        Returns:
            提取的表格列表
        """
        try:
            from app.tools.table_extractors.pdfplumber_extractor import PDFPlumberTableExtractor

            logger.info("using_pdfplumber_fallback")

            fallback = PDFPlumberTableExtractor(self.config)
            return await fallback.extract_tables(pdf_source, **kwargs)

        except ImportError:
            logger.error("pdfplumber_not_available")
            return []
        except Exception as e:
            logger.error("fallback_extraction_failed", error=str(e))
            return []

    def is_available(self) -> bool:
        """
        检查MinerU提取器是否可用

        Returns:
            是否可用
        """
        return self._mineru_available

    def get_backend_info(self) -> Dict[str, Any]:
        """
        获取后端信息

        Returns:
            后端配置信息
        """
        return {
            "available": self._mineru_available,
            "backend": self.mineru_config.get("backend", "pipeline"),
            "table_model": self.mineru_config.get("table_model", "rapid_table"),
            "table_merge_enabled": self.mineru_config.get("enable_table_merge", True),
            "fallback_enabled": self.mineru_config.get("fallback_to_pdfplumber", True),
            "supported_backends": [
                "pipeline",  # 通用，支持CPU/GPU
                "vlm-auto-engine",  # 高精度VLM，需要GPU
                "hybrid-auto-engine",  # 混合模式
            ]
        }
