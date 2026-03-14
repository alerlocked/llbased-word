"""
表格验证器 - 质量验证和置信度评估
"""
from typing import List, Dict, Any, Optional
from app.models.table_models import ExtractedTable, TableValidationResult
from app.shared.logging import get_logger

logger = get_logger(__name__)


class TableValidator:
    """
    表格验证器

    对提取的表格进行质量验证和置信度评估
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化验证器

        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.min_confidence_threshold = self.config.get("min_confidence_threshold", 0.5)
        self.min_non_empty_ratio = self.config.get("min_non_empty_ratio", 0.7)

        logger.info("table_validator_initialized",
                   min_confidence=self.min_confidence_threshold,
                   min_non_empty_ratio=self.min_non_empty_ratio)

    def validate_table(
        self,
        table: ExtractedTable
    ) -> TableValidationResult:
        """
        验证单个表格

        Args:
            table: 提取的表格

        Returns:
            验证结果
        """
        try:
            issues = []
            warnings = []
            suggested_fixes = []

            # 1. 结构完整性检查
            has_consistent_columns = self._check_column_consistency(table, issues, warnings)
            has_valid_headers = self._check_headers(table, issues, warnings)
            has_complete_rows = self._check_row_completeness(table, issues, warnings)

            # 2. 内容质量检查
            non_empty_cell_ratio = self._calculate_non_empty_ratio(table)
            data_consistency_score = self._assess_data_consistency(table, warnings)

            # 3. 计算综合置信度
            confidence_score = self._calculate_overall_confidence(
                table,
                has_consistent_columns,
                has_valid_headers,
                has_complete_rows,
                non_empty_cell_ratio,
                data_consistency_score
            )

            # 4. 生成建议
            self._generate_suggestions(issues, warnings, suggested_fixes)

            # 5. 判断是否有效
            is_valid = (
                confidence_score >= self.min_confidence_threshold and
                has_consistent_columns and
                non_empty_cell_ratio >= self.min_non_empty_ratio
            )

            logger.info("table_validated",
                       table_id=table.table_id,
                       is_valid=is_valid,
                       confidence_score=confidence_score,
                       issues_count=len(issues),
                       warnings_count=len(warnings))

            return TableValidationResult(
                is_valid=is_valid,
                confidence_score=confidence_score,
                has_consistent_columns=has_consistent_columns,
                has_valid_headers=has_valid_headers,
                has_complete_rows=has_complete_rows,
                non_empty_cell_ratio=non_empty_cell_ratio,
                data_consistency_score=data_consistency_score,
                issues=issues,
                warnings=warnings,
                suggested_fixes=suggested_fixes
            )

        except Exception as e:
            logger.error("table_validation_failed",
                        table_id=table.table_id,
                        error=str(e))
            return TableValidationResult(
                is_valid=False,
                confidence_score=0.0,
                issues=[f"Validation error: {str(e)}"]
            )

    def validate_tables(
        self,
        tables: List[ExtractedTable]
    ) -> List[TableValidationResult]:
        """
        验证多个表格

        Args:
            tables: 表格列表

        Returns:
            验证结果列表
        """
        results = []
        for table in tables:
            result = self.validate_table(table)
            results.append(result)

        valid_count = sum(1 for r in results if r.is_valid)
        logger.info("tables_validation_completed",
                   total_tables=len(tables),
                   valid_tables=valid_count,
                   avg_confidence=sum(r.confidence_score for r in results) / len(results) if results else 0)

        return results

    def _check_column_consistency(
        self,
        table: ExtractedTable,
        issues: List[str],
        warnings: List[str]
    ) -> bool:
        """
        检查列一致性

        Args:
            table: 表格
            issues: 问题列表
            warnings: 警告列表

        Returns:
            是否一致
        """
        if not table.rows:
            issues.append("Empty table - no rows found")
            return False

        expected_columns = table.columns
        inconsistent_rows = []

        for row_idx, row in enumerate(table.rows):
            if len(row) != expected_columns:
                inconsistent_rows.append(row_idx)

        if inconsistent_rows:
            issue = f"Inconsistent column count in rows: {inconsistent_rows[:5]}"  # 只显示前5个
            if len(inconsistent_rows) > len(table.rows) * 0.1:  # 超过10%不一致
                issues.append(issue)
                return False
            else:
                warnings.append(issue)

        return len(inconsistent_rows) == 0

    def _check_headers(
        self,
        table: ExtractedTable,
        issues: List[str],
        warnings: List[str]
    ) -> bool:
        """
        检查表头有效性

        Args:
            table: 表格
            issues: 问题列表
            warnings: 警告列表

        Returns:
            是否有效
        """
        if not table.headers:
            warnings.append("No headers detected")
            return False

        # 检查表头是否全为空
        empty_headers = sum(1 for h in table.headers if not h or str(h).strip() == "")
        if empty_headers == len(table.headers):
            issues.append("All header cells are empty")
            return False

        # 检查是否有重复的表头
        header_set = set(str(h).strip().lower() for h in table.headers if h)
        if len(header_set) < len([h for h in table.headers if h]):
            warnings.append("Duplicate headers detected")

        return True

    def _check_row_completeness(
        self,
        table: ExtractedTable,
        issues: List[str],
        warnings: List[str]
    ) -> bool:
        """
        检查行完整性

        Args:
            table: 表格
            issues: 问题列表
            warnings: 警告列表

        Returns:
            是否完整
        """
        if not table.rows:
            return False

        empty_rows = sum(1 for row in table.rows if not row or all(not cell or str(cell).strip() == "" for cell in row))

        if empty_rows > 0:
            ratio = empty_rows / len(table.rows)
            if ratio > 0.2:  # 超过20%的空行
                warnings.append(f"High ratio of empty rows: {empty_rows}/{len(table.rows)} ({ratio:.1%})")

        return True

    def _calculate_non_empty_ratio(self, table: ExtractedTable) -> float:
        """
        计算非空单元格比例

        Args:
            table: 表格

        Returns:
            非空单元格比例 (0-1)
        """
        if not table.rows:
            return 0.0

        total_cells = sum(len(row) for row in table.rows)
        if total_cells == 0:
            return 0.0

        non_empty_cells = sum(
            1 for row in table.rows
            for cell in row
            if cell and str(cell).strip()
        )

        return non_empty_cells / total_cells

    def _assess_data_consistency(
        self,
        table: ExtractedTable,
        warnings: List[str]
    ) -> float:
        """
        评估数据一致性

        Args:
            table: 表格
            warnings: 警告列表

        Returns:
            一致性分数 (0-1)
        """
        if not table.data_rows or len(table.data_rows) == 0:
            return 1.0

        scores = []

        # 检查每列的数据类型一致性
        if table.headers:
            for col_idx in range(len(table.headers)):
                col_values = [
                    row[col_idx] if col_idx < len(row) else None
                    for row in table.data_rows
                    if row
                ]

                if col_values:
                    consistency = self._check_column_data_consistency(col_values)
                    scores.append(consistency)

        if not scores:
            return 1.0

        avg_consistency = sum(scores) / len(scores)

        if avg_consistency < 0.7:
            warnings.append(f"Low data consistency score: {avg_consistency:.2f}")

        return avg_consistency

    def _check_column_data_consistency(self, column_values: List[Any]) -> float:
        """
        检查单列数据一致性

        Args:
            column_values: 列值列表

        Returns:
            一致性分数 (0-1)
        """
        if not column_values:
            return 1.0

        # 推断主要数据类型
        type_counts = {
            "empty": 0,
            "number": 0,
            "text": 0,
            "mixed": 0
        }

        for value in column_values:
            if value is None or str(value).strip() == "":
                type_counts["empty"] += 1
            else:
                value_str = str(value).strip()
                # 简单类型检测
                if value_str.replace(".", "").replace("-", "").isdigit():
                    type_counts["number"] += 1
                elif any(c.isalpha() for c in value_str):
                    type_counts["text"] += 1
                else:
                    type_counts["mixed"] += 1

        # 计算主要类型占比
        non_empty_total = sum(type_counts.values()) - type_counts["empty"]
        if non_empty_total == 0:
            return 1.0

        max_type_count = max(
            type_counts["number"],
            type_counts["text"],
            type_counts["mixed"]
        )

        return max_type_count / non_empty_total

    def _calculate_overall_confidence(
        self,
        table: ExtractedTable,
        has_consistent_columns: bool,
        has_valid_headers: bool,
        has_complete_rows: bool,
        non_empty_cell_ratio: float,
        data_consistency_score: float
    ) -> float:
        """
        计算综合置信度

        Args:
            table: 表格
            has_consistent_columns: 列是否一致
            has_valid_headers: 表头是否有效
            has_complete_rows: 行是否完整
            non_empty_cell_ratio: 非空单元格比例
            data_consistency_score: 数据一致性分数

        Returns:
            综合置信度 (0-1)
        """
        score = table.confidence_score  # 基础分数

        # 结构性惩罚
        if not has_consistent_columns:
            score *= 0.5
        if not has_valid_headers:
            score *= 0.9
        if not has_complete_rows:
            score *= 0.95

        # 内容质量加权
        score = score * 0.6 + non_empty_cell_ratio * 0.2 + data_consistency_score * 0.2

        return min(max(score, 0.0), 1.0)  # 限制在0-1之间

    def _generate_suggestions(
        self,
        issues: List[str],
        warnings: List[str],
        suggested_fixes: List[str]
    ) -> None:
        """
        生成修复建议

        Args:
            issues: 问题列表
            warnings: 警告列表
            suggested_fixes: 建议列表
        """
        # 基于问题生成建议
        for issue in issues:
            if "Inconsistent column count" in issue:
                suggested_fixes.append("Check for merged cells or missing data")
            elif "All header cells are empty" in issue:
                suggested_fixes.append("Verify table boundaries and extraction settings")
            elif "Empty table" in issue:
                suggested_fixes.append("Check if this region contains a table")

        # 基于警告生成建议
        for warning in warnings:
            if "Duplicate headers" in warning:
                suggested_fixes.append("Review header row detection logic")
            elif "empty rows" in warning.lower():
                suggested_fixes.append("Consider removing empty rows from output")
            elif "data consistency" in warning.lower():
                suggested_fixes.append("Verify data format and consider manual review")

        # 去重
        suggested_fixes = list(set(suggested_fixes))
