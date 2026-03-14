"""
表格合并器 - 检测和合并跨页表格
"""
from typing import List, Dict, Any, Optional, Tuple
from app.models.table_models import ExtractedTable, TableMetadata
from app.shared.logging import get_logger

logger = get_logger(__name__)


class TableMerger:
    """
    表格合并器

    检测和合并跨越多个页面的表格
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化合并器

        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.column_similarity_threshold = self.config.get("column_similarity_threshold", 0.8)
        self.header_match_threshold = self.config.get("header_match_threshold", 0.9)

        logger.info("table_merger_initialized",
                   column_threshold=self.column_similarity_threshold,
                   header_threshold=self.header_match_threshold)

    def detect_and_merge_tables(
        self,
        tables: List[ExtractedTable]
    ) -> List[ExtractedTable]:
        """
        检测并合并跨页表格

        Args:
            tables: 提取的表格列表

        Returns:
            合并后的表格列表
        """
        if not tables or len(tables) <= 1:
            return tables

        # 按页码排序
        sorted_tables = sorted(tables, key=lambda t: t.page_number)

        merged_tables = []
        current_table = None

        for table in sorted_tables:
            if current_table is None:
                current_table = table
                continue

            # 检查是否是continuation
            if self.detect_continuation(current_table, table):
                # 合并表格
                current_table = self.merge_two_tables(current_table, table)
                logger.info("tables_merged",
                           table1_id=current_table.table_id,
                           table2_id=table.table_id,
                           merged_rows=len(current_table.rows))
            else:
                # 保存当前表格，开始新的表格
                merged_tables.append(current_table)
                current_table = table

        # 添加最后一个表格
        if current_table is not None:
            merged_tables.append(current_table)

        logger.info("table_merging_completed",
                   original_count=len(tables),
                   merged_count=len(merged_tables),
                   merged_pairs=len(tables) - len(merged_tables))

        return merged_tables

    def detect_continuation(
        self,
        table1: ExtractedTable,
        table2: ExtractedTable
    ) -> bool:
        """
        检测table2是否是table1的延续

        Args:
            table1: 第一个表格
            table2: 第二个表格

        Returns:
            是否是延续
        """
        try:
            # 检查1: 页码连续性
            if table2.page_number != table1.page_number + 1:
                return False

            # 检查2: 列数匹配
            if table2.columns != table1.columns:
                logger.debug("column_count_mismatch",
                           table1_cols=table1.columns,
                           table2_cols=table2.columns)
                return False

            # 检查3: 列结构相似性
            if not self._check_column_similarity(table1, table2):
                logger.debug("column_structure_dissimilar")
                return False

            # 检查4: 表头重复或缺失
            header_match = self._check_header_match(table1, table2)

            # 如果表头匹配，说明是新表格的开始
            if header_match > self.header_match_threshold:
                logger.debug("headers_match_new_table")
                return False

            # 检查5: 位置一致性（表格在页面上的位置）
            if not self._check_position_consistency(table1, table2):
                logger.debug("position_inconsistent")
                return False

            return True

        except Exception as e:
            logger.warning("continuation_detection_failed",
                          table1_id=table1.table_id,
                          table2_id=table2.table_id,
                          error=str(e))
            return False

    def merge_two_tables(
        self,
        table1: ExtractedTable,
        table2: ExtractedTable
    ) -> ExtractedTable:
        """
        合并两个表格

        Args:
            table1: 第一个表格
            table2: 第二个表格

        Returns:
            合并后的表格
        """
        try:
            # 合并行数据
            # 检查table2的第一行是否是重复的表头
            rows_to_add = table2.rows

            if table2.headers and self._is_header_row(table2.rows[0], table2.headers):
                # 跳过重复的表头
                rows_to_add = table2.rows[1:]
                logger.debug("skipping_duplicate_header", table_id=table2.table_id)

            merged_rows = table1.rows + rows_to_add

            # 创建新的元数据
            merged_metadata = TableMetadata(
                has_merged_cells=table1.metadata.has_merged_cells or table2.metadata.has_merged_cells,
                is_continuation=False,
                has_border=table1.metadata.has_border and table2.metadata.has_border,
                is_rotated=table1.metadata.is_rotated or table2.metadata.is_rotated,
                confidence_score=min(table1.confidence_score, table2.confidence_score),
                extraction_method=f"{table1.extraction_method}+merged"
            )

            # 创建合并后的表格
            merged_table = ExtractedTable(
                table_id=table1.table_id,
                page_number=table1.page_number,
                bbox=table1.bbox,  # 使用第一个表格的bbox
                rows=merged_rows,
                columns=table1.columns,
                headers=table1.headers,
                confidence_score=(table1.confidence_score + table2.confidence_score) / 2,
                extraction_method="merged",
                parser_used=table1.parser_used,
                metadata=merged_metadata,
                table_type=table1.table_type
            )

            logger.info("tables_merged_successfully",
                       table1_id=table1.table_id,
                       table2_id=table2.table_id,
                       merged_table_id=merged_table.table_id,
                       total_rows=len(merged_rows))

            return merged_table

        except Exception as e:
            logger.error("table_merge_failed",
                        table1_id=table1.table_id,
                        table2_id=table2.table_id,
                        error=str(e))
            # 返回第一个表格
            return table1

    def _check_column_similarity(
        self,
        table1: ExtractedTable,
        table2: ExtractedTable
    ) -> bool:
        """
        检查两个表格的列结构相似性

        Args:
            table1: 第一个表格
            table2: 第二个表格

        Returns:
            是否相似
        """
        if not table1.rows or not table2.rows:
            return False

        # 比较列宽
        # 简化方法：比较第一行的单元格文本长度分布
        row1 = table1.rows[0]
        row2 = table2.rows[0]

        if len(row1) != len(row2):
            return False

        # 计算相似度
        similarities = []
        for cell1, cell2 in zip(row1, row2):
            len1 = len(str(cell1)) if cell1 else 0
            len2 = len(str(cell2)) if cell2 else 0

            if len1 == 0 and len2 == 0:
                similarities.append(1.0)
            elif len1 == 0 or len2 == 0:
                similarities.append(0.0)
            else:
                similarity = min(len1, len2) / max(len1, len2)
                similarities.append(similarity)

        avg_similarity = sum(similarities) / len(similarities)
        return avg_similarity >= self.column_similarity_threshold

    def _check_header_match(
        self,
        table1: ExtractedTable,
        table2: ExtractedTable
    ) -> float:
        """
        检查表头匹配度

        Args:
            table1: 第一个表格
            table2: 第二个表格

        Returns:
            匹配度 (0-1)
        """
        if not table1.headers or not table2.headers:
            return 0.0

        if len(table1.headers) != len(table2.headers):
            return 0.0

        matches = 0
        for h1, h2 in zip(table1.headers, table2.headers):
            # 标准化比较
            h1_norm = str(h1).strip().lower() if h1 else ""
            h2_norm = str(h2).strip().lower() if h2 else ""

            if h1_norm == h2_norm:
                matches += 1
            elif h1_norm in h2_norm or h2_norm in h1_norm:
                matches += 0.5  # 部分匹配

        return matches / len(table1.headers)

    def _check_position_consistency(
        self,
        table1: ExtractedTable,
        table2: ExtractedTable
    ) -> bool:
        """
        检查位置一致性

        Args:
            table1: 第一个表格
            table2: 第二个表格

        Returns:
            是否一致
        """
        # 比较表格在页面上的水平位置
        # table1.bbox: (x0, y0, x1, y1)
        # 检查x坐标是否接近

        x0_diff = abs(table1.bbox[0] - table2.bbox[0])
        x1_diff = abs(table1.bbox[2] - table2.bbox[2])

        # 允许一定的偏差（例如10像素）
        position_threshold = 10.0

        return x0_diff < position_threshold and x1_diff < position_threshold

    def _is_header_row(
        self,
        row: List[str],
        headers: List[str]
    ) -> bool:
        """
        判断一行是否是表头行

        Args:
            row: 行数据
            headers: 表头

        Returns:
            是否是表头行
        """
        if not row or not headers:
            return False

        if len(row) != len(headers):
            return False

        matches = sum(
            1 for cell, header in zip(row, headers)
            if str(cell).strip().lower() == str(header).strip().lower()
        )

        return matches == len(headers)

    def merge_tables(
        self,
        table_list: List[ExtractedTable]
    ) -> List[ExtractedTable]:
        """
        合并表格列表（detect_and_merge_tables的别名）

        Args:
            table_list: 表格列表

        Returns:
            合并后的表格列表
        """
        return self.detect_and_merge_tables(table_list)
