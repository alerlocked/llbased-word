"""
解析器选择器 - 双复杂度模式选择

简化为两种模式：
- SIMPLE (简单模式): 无表格，使用PyMuPDF快速解析
- COMPLEX (复杂模式): 有表格，使用MinerU-VLM高精度解析
"""
import fitz  # PyMuPDF
from typing import Dict, Any, Optional, Union
from pathlib import Path

from app.models.table_models import ParserType, ParserSelectionResult
from app.shared.logging import get_logger

logger = get_logger(__name__)


class ParserSelector:
    """
    解析器选择器 - 双复杂度模式

    快速检测PDF是否有表格，选择合适的解析模式：
    - 无表格 → SIMPLE (PyMuPDF快速解析)
    - 有表格 → COMPLEX (MinerU-VLM高精度解析)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化选择器

        Args:
            config: 配置参数（可选，用于覆盖默认行为）
        """
        self.config = config or {}

        # 检查MinerU是否可用
        self._mineru_available = self._check_mineru_available()

        logger.info("parser_selector_initialized",
                   mineru_available=self._mineru_available)

    async def select_parser(
        self,
        pdf_source: Union[str, bytes, Path],
        force_mode: Optional[str] = None
    ) -> ParserSelectionResult:
        """
        选择解析模式

        Args:
            pdf_source: PDF文件路径或二进制数据
            force_mode: 强制模式 ("simple" | "complex" | None)
                       None表示自动检测

        Returns:
            解析器选择结果
        """
        try:
            # 强制模式
            if force_mode:
                return self._create_forced_result(force_mode)

            # 快速检测是否有表格
            has_tables, table_count = await self.quick_detect_tables(pdf_source)

            # 选择模式
            if has_tables and self._mineru_available:
                selected_parser = ParserType.COMPLEX
                reasoning = f"检测到{table_count}个表格，使用MinerU-VLM高精度解析"
            else:
                selected_parser = ParserType.SIMPLE
                if has_tables and not self._mineru_available:
                    reasoning = f"检测到{table_count}个表格，但MinerU不可用，使用PyMuPDF解析"
                else:
                    reasoning = "未检测到表格，使用PyMuPDF快速解析"

            logger.info("parser_selected",
                       mode=selected_parser.value,
                       has_tables=has_tables,
                       table_count=table_count)

            return ParserSelectionResult(
                selected_parser=selected_parser,
                has_tables=has_tables,
                table_count=table_count,
                reasoning=reasoning
            )

        except Exception as e:
            logger.error("parser_selection_failed", error=str(e))
            # 出错时默认使用简单模式
            return ParserSelectionResult(
                selected_parser=ParserType.SIMPLE,
                has_tables=False,
                reasoning=f"检测失败，使用默认简单模式: {str(e)}"
            )

    async def quick_detect_tables(
        self,
        pdf_source: Union[str, bytes, Path]
    ) -> tuple[bool, int]:
        """
        快速检测PDF是否有表格

        使用PyMuPDF的find_tables()方法快速扫描，
        只检测前几页以提高速度。

        Args:
            pdf_source: PDF源

        Returns:
            (has_tables, table_count) 元组
        """
        try:
            # 打开PDF
            if isinstance(pdf_source, (str, Path)):
                doc = fitz.open(pdf_source)
            else:
                doc = fitz.open(stream=pdf_source, filetype="pdf")

            total_tables = 0
            # 只检测前5页或全部页面（取较小值）
            pages_to_check = min(len(doc), 5)

            for page_num in range(pages_to_check):
                page = doc[page_num]
                tables = page.find_tables()
                # TableFinder对象需要转换为列表或使用.tables属性
                if hasattr(tables, 'tables'):
                    total_tables += len(tables.tables)
                else:
                    total_tables += len(list(tables))

            doc.close()

            has_tables = total_tables > 0

            logger.debug("table_detection_completed",
                        pages_checked=pages_to_check,
                        tables_found=total_tables,
                        has_tables=has_tables)

            return has_tables, total_tables

        except Exception as e:
            logger.warning("table_detection_failed", error=str(e))
            return False, 0

    def _create_forced_result(self, force_mode: str) -> ParserSelectionResult:
        """
        创建强制模式的结果

        Args:
            force_mode: 强制的模式 ("simple" | "complex")

        Returns:
            解析器选择结果
        """
        if force_mode.lower() == "complex":
            if not self._mineru_available:
                logger.warning("force_complex_but_mineru_unavailable")
            return ParserSelectionResult(
                selected_parser=ParserType.COMPLEX,
                has_tables=True,  # 假设有表格
                table_count=-1,   # 未知
                reasoning="强制使用复杂模式"
            )
        else:
            return ParserSelectionResult(
                selected_parser=ParserType.SIMPLE,
                has_tables=False,
                reasoning="强制使用简单模式"
            )

    def _check_mineru_available(self) -> bool:
        """
        检查MinerU是否可用

        Returns:
            MinerU是否可用
        """
        try:
            from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor
            # 尝试实例化以验证依赖
            extractor = MinerUTableExtractor()
            return extractor.is_available()
        except ImportError:
            return False
        except Exception:
            return False

    # ============ 向后兼容方法 ============

    async def _analyze_document(
        self,
        pdf_source: Union[str, bytes, Path],
        page_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        分析文档特征（向后兼容）

        Args:
            pdf_source: PDF源
            page_number: 页码

        Returns:
            分析结果
        """
        has_tables, table_count = await self.quick_detect_tables(pdf_source)

        return {
            "table_count": table_count,
            "has_borderless_tables": False,
            "has_merged_cells": False,
            "has_multipage_tables": False,
            "chinese_content_ratio": 0.0
        }

    def _calculate_complexity_score(self, analysis: Dict[str, Any]) -> float:
        """计算复杂度分数（向后兼容）"""
        return 0.8 if analysis.get("table_count", 0) > 0 else 0.2

    def _determine_parser(self, complexity_score: float) -> ParserType:
        """确定解析器（向后兼容）"""
        return ParserType.COMPLEX if complexity_score > 0.5 else ParserType.SIMPLE

    def _generate_reasoning(
        self,
        parser: ParserType,
        complexity_score: float,
        analysis: Dict[str, Any]
    ) -> str:
        """生成选择理由（向后兼容）"""
        if parser == ParserType.COMPLEX:
            return f"检测到表格，使用复杂模式"
        return "无表格，使用简单模式"
