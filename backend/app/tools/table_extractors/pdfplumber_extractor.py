"""
PDFPlumber表格提取器 - 基于pdfplumber的高精度表格提取
"""
import pdfplumber
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

from app.tools.table_extractors.base_extractor import BaseTableExtractor
from app.models.table_models import ExtractedTable, TableMetadata, ParserType, TableType
from app.shared.logging import get_logger

logger = get_logger(__name__)


class PDFPlumberTableExtractor(BaseTableExtractor):
    """
    PDFPlumber表格提取器

    使用pdfplumber实现高精度的表格提取，
    特别擅长处理复杂表格、无边框表格和中文内容
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化PDFPlumber提取器

        Args:
            config: 配置参数
                - table_settings: pdfplumber表格提取设置
                - extract_images: 是否提取图像
        """
        super().__init__(config)

        # pdfplumber表格提取设置
        # 不指定策略，让 pdfplumber 自动检测（表格线优先，回退到文本）
        # 这样可以同时处理有表格线和无表格线的表格
        self.table_settings = self.config.get("table_settings", {})

        logger.info("pdfplumber_extractor_initialized",
                   table_settings_keys=list(self.table_settings.keys()))

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
                - pages: 指定页码列表 (默认所有页)
                - table_settings: 临时表格设置

        Returns:
            提取的表格列表
        """
        try:
            # 打开PDF
            if isinstance(pdf_source, (str, Path)):
                pdf = pdfplumber.open(pdf_source)
            else:
                pdf = pdfplumber.open(pdf_source)

            tables = []
            pages_to_process = kwargs.get("pages", range(len(pdf.pages)))
            custom_settings = kwargs.get("table_settings", self.table_settings)

            logger.info("pdfplumber_extraction_started",
                       total_pages=len(pdf.pages),
                       pages_to_process=len(list(pages_to_process)) if hasattr(pages_to_process, '__len__') else 'all')

            # 处理每一页
            for page_num in range(len(pdf.pages)):
                if page_num not in pages_to_process:
                    continue

                page = pdf.pages[page_num]
                page_tables = await self._extract_tables_from_page(
                    page,
                    page_num,
                    custom_settings
                )
                tables.extend(page_tables)

            pdf.close()

            logger.info("pdfplumber_extraction_completed",
                       total_tables=len(tables),
                       avg_confidence=sum(t.confidence_score for t in tables) / len(tables) if tables else 0)

            return tables

        except Exception as e:
            logger.error("pdfplumber_extraction_failed", error=str(e))
            raise

    async def _extract_tables_from_page(
        self,
        page: pdfplumber.pdf.Page,
        page_num: int,
        table_settings: Dict[str, Any]
    ) -> List[ExtractedTable]:
        """
        从单个页面提取表格

        Args:
            page: pdfplumber页面对象
            page_num: 页码
            table_settings: 表格设置

        Returns:
            该页的表格列表
        """
        try:
            # 使用pdfplumber提取表格
            raw_tables = page.find_tables(table_settings=table_settings)

            if not raw_tables:
                logger.debug("no_tables_found_page", page_number=page_num)
                return []

            extracted_tables = []

            for table_index, table in enumerate(raw_tables):
                # 提取表格数据
                table_data = table.extract()

                if not table_data or len(table_data) == 0:
                    continue

                # 检测是否有合并单元格
                has_merged_cells = self._detect_merged_cells(table, table_data)

                # 计算置信度
                confidence = self._calculate_confidence_score(table_data)

                # 检测表格类型
                table_type_str = self._detect_table_type(table_data[0] if table_data else None)
                table_type = TableType(table_type_str)

                # 创建表格元数据
                metadata = TableMetadata(
                    has_merged_cells=has_merged_cells,
                    has_border=self._has_border(table),
                    confidence_score=confidence,
                    extraction_method="pdfplumber"
                )

                # 创建ExtractedTable实例
                extracted_table = ExtractedTable(
                    table_id=self._generate_table_id(page_num, table_index),
                    page_number=page_num,
                    bbox=table.bbox,
                    rows=table_data,
                    columns=len(table_data[0]) if table_data else 0,
                    confidence_score=confidence,
                    extraction_method="pdfplumber",
                    parser_used=ParserType.PDFPLUMBER,
                    metadata=metadata,
                    table_type=table_type
                )

                extracted_tables.append(extracted_table)

            logger.info("tables_extracted_from_page",
                       page_number=page_num,
                       table_count=len(extracted_tables))

            return extracted_tables

        except Exception as e:
            logger.warning("page_table_extraction_failed",
                          page_number=page_num,
                          error=str(e))
            return []

    def _detect_merged_cells(
        self,
        table: pdfplumber.table.Table,
        table_data: List[List[str]]
    ) -> bool:
        """
        检测表格中是否有合并单元格

        Args:
            table: pdfplumber表格对象
            table_data: 表格数据

        Returns:
            是否有合并单元格
        """
        # 检查单元格是否跨多列或多行
        # pdfplumber会显示合并单元格的内容可能重复或为None
        try:
            # 简单的启发式方法：检查是否有过多的None或重复值
            none_count = sum(1 for row in table_data for cell in row if cell is None)
            total_cells = sum(len(row) for row in table_data)

            # 如果None单元格超过5%，可能有合并单元格
            return (none_count / total_cells) > 0.05 if total_cells > 0 else False

        except Exception:
            return False

    def _has_border(self, table: pdfplumber.table.Table) -> bool:
        """
        检测表格是否有边框

        Args:
            table: pdfplumber表格对象

        Returns:
            是否有边框
        """
        # pdfplumber的table对象包含lines属性
        # 如果有足够的线条，说明有边框
        try:
            # 简单启发式：检查bbox是否合理
            # 有边框的表格通常有明确的bbox
            return table.bbox is not None and all(v > 0 for v in table.bbox)
        except Exception:
            return True  # 默认假设有边框

    def _extract_table_with_settings(
        self,
        page: pdfplumber.pdf.Page,
        settings: Dict[str, Any]
    ) -> List[List[List[str]]]:
        """
        使用自定义设置提取表格

        Args:
            page: pdfplumber页面对象
            settings: 表格提取设置

        Returns:
            表格数据列表
        """
        try:
            tables = page.find_tables(table_settings=settings)
            return [table.extract() for table in tables if table.extract()]

        except Exception as e:
            logger.warning("custom_table_extraction_failed", error=str(e))
            return []

    def optimize_settings_for_chinese(
        self,
        page: pdfplumber.pdf.Page
    ) -> Dict[str, Any]:
        """
        针对中文内容优化的表格提取设置

        Args:
            page: pdfplumber页面对象

        Returns:
            优化的设置
        """
        # 针对中文PDF的优化设置
        chinese_settings = {
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
            "snap_tolerance": 5,  # 增加容差
            "join_tolerance": 5,
            "min_words_vertical": 1,
            "min_words_horizontal": 1,
            "intersection_y_tolerance": 5,
            "intersection_x_tolerance": 5,
        }

        return chinese_settings
