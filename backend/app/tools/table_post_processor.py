"""
表格后处理器 - 智能合并多余列

针对工艺文件PDF的表格特点：
- 原始提取通常有20+列（因为合并单元格被拆分）
- 实际应该是6-8列
- 通过分析内容模式来智能合并
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import re


@dataclass
class TableColumn:
    """表格列信息"""
    index: int
    header: str
    content_samples: List[str]
    is_empty: bool = False
    is_fragment: bool = False  # 是否是碎片列（应该合并到前一列）


class TablePostProcessor:
    """
    表格后处理器

    智能合并pdfplumber提取的多余列
    """

    # 工艺文件常见列名模式
    KNOWN_HEADERS = [
        r"序\s*号",
        r"工\s*艺\s*文\s*件\s*名\s*称",
        r"工\s*艺\s*文\s*件\s*编\s*号",
        r"零.*部.*件.*代\s*号",
        r"零.*部.*件.*名\s*称",
        r"页\s*数",
        r"备\s*注",
        r"代\s*号",
        r"名\s*称",
        r"数\s*量",
        r"规\s*格",
        r"材\s*料",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.target_columns = self.config.get("target_columns", 7)
        self.merge_threshold = self.config.get("merge_threshold", 0.7)

    def process_table(self, table: List[List[str]]) -> List[List[str]]:
        """
        处理表格，合并多余列

        Args:
            table: 原始表格数据

        Returns:
            处理后的表格
        """
        if not table or not table[0]:
            return table

        original_cols = len(table[0])

        # 如果列数合理，直接返回
        if original_cols <= self.target_columns + 2:
            return table

        # 分析列结构
        columns = self._analyze_columns(table)

        # 确定合并策略
        merge_plan = self._create_merge_plan(columns)

        # 执行合并
        return self._merge_columns(table, merge_plan)

    def _analyze_columns(self, table: List[List[str]]) -> List[TableColumn]:
        """分析每列的特征"""
        columns = []

        for col_idx in range(len(table[0])):
            # 提取列内容
            col_content = []
            for row in table:
                if col_idx < len(row):
                    cell = row[col_idx]
                    if cell and str(cell).strip():
                        col_content.append(str(cell).strip())

            # 判断是否是空列
            is_empty = len(col_content) == 0

            # 判断是否是碎片列（内容很短，可能是被拆分的部分）
            is_fragment = False
            if col_content and not is_empty:
                avg_len = sum(len(c) for c in col_content) / len(col_content)
                is_fragment = avg_len < 2  # 平均长度小于2个字符

            # 获取表头
            header = ""
            if table and col_idx < len(table[0]):
                header = str(table[0][col_idx] or "").strip()

            columns.append(TableColumn(
                index=col_idx,
                header=header,
                content_samples=col_content[:10],  # 只保存前10个样本
                is_empty=is_empty,
                is_fragment=is_fragment
            ))

        return columns

    def _create_merge_plan(self, columns: List[TableColumn]) -> List[Tuple[int, int]]:
        """
        创建合并计划

        Returns:
            [(源列索引, 目标列索引), ...]
        """
        merge_plan = []

        # 策略1：合并空列到前一列
        for i, col in enumerate(columns):
            if col.is_empty and i > 0:
                merge_plan.append((i, i - 1))

        # 策略2：合并碎片列到前一列
        for i, col in enumerate(columns):
            if col.is_fragment and i > 0 and (i, i-1) not in merge_plan:
                # 检查前一列是否也是碎片
                if columns[i-1].is_fragment or not columns[i-1].is_empty:
                    merge_plan.append((i, i - 1))

        # 策略3：基于内容模式识别
        # 找出主要列（包含完整信息的列）
        main_columns = []
        for i, col in enumerate(columns):
            if not col.is_empty and not col.is_fragment:
                # 检查是否匹配已知表头模式
                for pattern in self.KNOWN_HEADERS:
                    if re.search(pattern, col.header, re.IGNORECASE):
                        main_columns.append(i)
                        break
                else:
                    # 检查内容丰富度
                    if col.content_samples and len(col.content_samples[0]) > 3:
                        main_columns.append(i)

        return merge_plan

    def _merge_columns(self, table: List[List[str]], merge_plan: List[Tuple[int, int]]) -> List[List[str]]:
        """执行列合并"""
        if not merge_plan:
            return table

        # 构建新列映射
        cols_to_remove = set(src for src, _ in merge_plan)

        result = []
        for row in table:
            new_row = []
            for col_idx, cell in enumerate(row):
                if col_idx in cols_to_remove:
                    # 找到目标列并合并内容
                    for src, tgt in merge_plan:
                        if src == col_idx:
                            if tgt < len(new_row):
                                new_row[tgt] = str(new_row[tgt]) + str(cell)
                            break
                else:
                    # 调整索引（因为前面的列被删除了）
                    adjusted_idx = col_idx - sum(1 for src, _ in merge_plan if src < col_idx)
                    if adjusted_idx == len(new_row):
                        new_row.append(cell)
                    elif adjusted_idx < len(new_row):
                        # 可能需要合并
                        pass
                    else:
                        new_row.append(cell)

            result.append(new_row)

        return result


def clean_table(table: List[List[str]]) -> List[List[str]]:
    """
    清理表格

    - 移除完全空的行
    - 移除完全空的列
    - 清理单元格内容
    """
    if not table:
        return table

    # 移除空行
    cleaned = []
    for row in table:
        if any(cell and str(cell).strip() for cell in row):
            cleaned.append([str(cell).strip() if cell else "" for cell in row])

    if not cleaned:
        return cleaned

    # 移除空列
    num_cols = max(len(row) for row in cleaned)
    empty_cols = []

    for col_idx in range(num_cols):
        is_empty = True
        for row in cleaned:
            if col_idx < len(row) and row[col_idx] and row[col_idx].strip():
                is_empty = False
                break
        if is_empty:
            empty_cols.append(col_idx)

    if empty_cols:
        result = []
        for row in cleaned:
            new_row = [cell for idx, cell in enumerate(row) if idx not in empty_cols]
            result.append(new_row)
        return result

    return cleaned


def extract_catalog_table_smart(table: List[List[str]]) -> List[Dict[str, str]]:
    """
    智能提取目录表格

    工艺文件目录的典型结构：
    | 序号 | 文件名称 | 文件编号 | 零件代号 | 零件名称 | 页数 | 备注 |

    Args:
        table: 原始表格数据

    Returns:
        结构化的目录数据
    """
    if not table or len(table) < 2:
        return []

    result = []

    # 跳过表头
    for row in table[1:]:
        if not row:
            continue

        # 尝试识别序号（第一个数字）
        seq_num = None
        content_start_idx = 0

        for i, cell in enumerate(row):
            if cell and str(cell).strip().isdigit():
                seq_num = int(cell.strip())
                content_start_idx = i + 1
                break

        if seq_num is None:
            continue

        # 提取文件名（通常是接下来的几个非空单元格）
        file_name_parts = []
        for cell in row[content_start_idx:]:
            if cell and str(cell).strip():
                # 检查是否是文件编号（包含.S或数字.数字）
                if re.search(r'\d+\.\w+|S\d+', str(cell)):
                    break
                file_name_parts.append(str(cell).strip())

        file_name = " ".join(file_name_parts)

        result.append({
            "序号": seq_num,
            "文件名称": file_name,
            "原始行": row
        })

    return result
