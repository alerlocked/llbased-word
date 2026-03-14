"""
基础表格提取器 - 抽象基类
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

from app.models.table_models import ExtractedTable
from app.shared.logging import get_logger

logger = get_logger(__name__)


class BaseTableExtractor(ABC):
    """
    表格提取器基类

    定义所有表格提取器的通用接口
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化提取器

        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.min_confidence_threshold = self.config.get("min_confidence_threshold", 0.5)

        logger.info("table_extractor_initialized",
                   extractor_type=self.__class__.__name__,
                   config_keys=list(self.config.keys()))

    @abstractmethod
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

        Returns:
            提取的表格列表
        """
        pass

    def _generate_table_id(self, page_number: int, table_index: int) -> str:
        """
        生成表格ID

        Args:
            page_number: 页码
            table_index: 表格索引

        Returns:
            表格ID
        """
        return f"table_{page_number}_{table_index}"

    def _calculate_confidence_score(
        self,
        rows: List[List[str]],
        has_headers: bool = True
    ) -> float:
        """
        计算表格置信度分数

        Args:
            rows: 表格行数据
            has_headers: 是否有表头

        Returns:
            置信度分数 (0-1)
        """
        if not rows or len(rows) == 0:
            return 0.0

        # 检查列一致性
        expected_cols = len(rows[0])
        consistent_rows = sum(1 for row in rows if len(row) == expected_cols)
        consistency_score = consistent_rows / len(rows) if rows else 0

        # 检查非空单元格比例
        non_empty_cells = sum(1 for row in rows for cell in row if cell and str(cell).strip())
        total_cells = sum(len(row) for row in rows)
        content_score = non_empty_cells / total_cells if total_cells > 0 else 0

        # 综合置信度 (60% 完整性 + 40% 内容)
        confidence = (consistency_score * 0.6 + content_score * 0.4)
        return min(confidence, 1.0)

    def _detect_table_type(self, headers: Optional[List[str]]) -> str:
        """
        检测表格类型

        Args:
            headers: 表头

        Returns:
            表格类型
        """
        if not headers:
            return "general_table"

        header_text = " ".join(str(h).lower() for h in headers if h)

        # 工艺过程表关键词
        process_keywords = ["工序", "步骤", "操作", "设备", "工艺", "工步"]
        # 材料表关键词
        material_keywords = ["材料", "牌号", "规格", "数量", "毛坯"]
        # 质量检查表关键词
        quality_keywords = ["检验", "质量", "合格", "标准", "检测"]

        # 计算各类型得分
        process_score = sum(1 for kw in process_keywords if kw in header_text)
        material_score = sum(1 for kw in material_keywords if kw in header_text)
        quality_score = sum(1 for kw in quality_keywords if kw in header_text)

        max_score = max(process_score, material_score, quality_score)

        if max_score == 0:
            return "general_table"

        if process_score == max_score:
            return "process_table"
        elif material_score == max_score:
            return "material_table"
        else:
            return "quality_table"
