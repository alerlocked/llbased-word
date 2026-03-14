"""
表格数据模型 - 统一的表格表示和验证结果
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum


class ParserType(Enum):
    """
    解析器类型 - 简化为两种模式

    SIMPLE: 简单模式，使用PyMuPDF快速解析（无表格或简单文档）
    COMPLEX: 复杂模式，使用MinerU-VLM高精度解析（有表格）
    """
    SIMPLE = "simple"      # 简单模式: PyMuPDF (无表格)
    COMPLEX = "complex"    # 复杂模式: MinerU-VLM (有表格)

    # 保留旧值用于向后兼容
    PYMUPDF = "simple"     # 别名
    PDFPLUMBER = "simple"  # 别名
    MINERU = "complex"     # 别名
    HYBRID = "complex"     # 别名


class TableType(Enum):
    """表格类型"""
    PROCESS_TABLE = "process_table"  # 工艺过程表
    MATERIAL_TABLE = "material_table"  # 材料表
    QUALITY_TABLE = "quality_table"  # 质量检查表
    GENERAL_TABLE = "general_table"  # 通用表格


@dataclass
class TableMetadata:
    """表格元数据"""
    has_merged_cells: bool = False
    is_continuation: bool = False
    continuation_of: Optional[str] = None  # 前续表格ID
    has_border: bool = True
    is_rotated: bool = False
    confidence_score: float = 0.0
    extraction_method: str = "unknown"  # "text_blocks", "table_detection", etc.


@dataclass
class ExtractedTable:
    """
    提取的表格数据模型

    统一PyMuPDF和pdfplumber的输出格式
    """
    table_id: str
    page_number: int
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    rows: List[List[str]]
    columns: int

    # 可选字段
    headers: Optional[List[str]] = None
    data_rows: Optional[List[List[str]]] = None
    confidence_score: float = 0.0

    # 解析器信息
    extraction_method: str = "unknown"
    parser_used: ParserType = ParserType.PYMUPDF

    # 元数据
    metadata: TableMetadata = field(default_factory=TableMetadata)

    # 表格类型
    table_type: TableType = TableType.GENERAL_TABLE

    def __post_init__(self):
        """初始化后处理"""
        # 自动分离表头和数据行
        if self.rows and len(self.rows) > 0:
            if self.headers is None:
                self.headers = self.rows[0] if self.rows else []
            if self.data_rows is None:
                self.data_rows = self.rows[1:] if len(self.rows) > 1 else []

        # 更新元数据中的置信度分数
        self.metadata.confidence_score = self.confidence_score
        self.metadata.extraction_method = self.extraction_method

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "table_id": self.table_id,
            "page_number": self.page_number,
            "bbox": list(self.bbox),
            "rows": self.rows,
            "columns": self.columns,
            "headers": self.headers,
            "data_rows": self.data_rows,
            "confidence_score": self.confidence_score,
            "extraction_method": self.extraction_method,
            "parser_used": self.parser_used.value,
            "metadata": {
                "has_merged_cells": self.metadata.has_merged_cells,
                "is_continuation": self.metadata.is_continuation,
                "continuation_of": self.metadata.continuation_of,
                "has_border": self.metadata.has_border,
                "is_rotated": self.metadata.is_rotated,
                "confidence_score": self.metadata.confidence_score,
                "extraction_method": self.metadata.extraction_method
            },
            "table_type": self.table_type.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExtractedTable':
        """从字典创建实例"""
        metadata_data = data.get("metadata", {})
        metadata = TableMetadata(
            has_merged_cells=metadata_data.get("has_merged_cells", False),
            is_continuation=metadata_data.get("is_continuation", False),
            continuation_of=metadata_data.get("continuation_of"),
            has_border=metadata_data.get("has_border", True),
            is_rotated=metadata_data.get("is_rotated", False),
            confidence_score=metadata_data.get("confidence_score", 0.0),
            extraction_method=metadata_data.get("extraction_method", "unknown")
        )

        return cls(
            table_id=data["table_id"],
            page_number=data["page_number"],
            bbox=tuple(data["bbox"]),
            rows=data["rows"],
            columns=data["columns"],
            headers=data.get("headers"),
            data_rows=data.get("data_rows"),
            confidence_score=data.get("confidence_score", 0.0),
            extraction_method=data.get("extraction_method", "unknown"),
            parser_used=ParserType(data.get("parser_used", "pymupdf")),
            metadata=metadata,
            table_type=TableType(data.get("table_type", "general_table"))
        )


@dataclass
class TableValidationResult:
    """表格验证结果"""
    is_valid: bool
    confidence_score: float

    # 结构完整性检查
    has_consistent_columns: bool = True
    has_valid_headers: bool = True
    has_complete_rows: bool = True

    # 内容质量检查
    non_empty_cell_ratio: float = 1.0
    data_consistency_score: float = 1.0

    # 问题列表
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # 建议的修复方案
    suggested_fixes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "is_valid": self.is_valid,
            "confidence_score": self.confidence_score,
            "structural_checks": {
                "has_consistent_columns": self.has_consistent_columns,
                "has_valid_headers": self.has_valid_headers,
                "has_complete_rows": self.has_complete_rows
            },
            "content_quality": {
                "non_empty_cell_ratio": self.non_empty_cell_ratio,
                "data_consistency_score": self.data_consistency_score
            },
            "issues": self.issues,
            "warnings": self.warnings,
            "suggested_fixes": self.suggested_fixes
        }


@dataclass
class ParserSelectionResult:
    """
    解析器选择结果 - 简化为双模式

    基于是否有表格快速选择解析模式：
    - has_tables=False → SIMPLE (PyMuPDF)
    - has_tables=True → COMPLEX (MinerU-VLM)
    """
    selected_parser: ParserType
    has_tables: bool
    table_count: int = 0
    reasoning: str = ""

    # 保留用于向后兼容
    complexity_score: float = 0.0
    has_borderless_tables: bool = False
    has_merged_cells: bool = False
    has_multipage_tables: bool = False
    chinese_content_ratio: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "selected_parser": self.selected_parser.value,
            "parser_mode": "simple" if self.selected_parser == ParserType.SIMPLE else "complex",
            "has_tables": self.has_tables,
            "table_count": self.table_count,
            "reasoning": self.reasoning,
            # 向后兼容
            "complexity_score": self.complexity_score,
            "analysis_details": {
                "table_count": self.table_count,
                "has_borderless_tables": self.has_borderless_tables,
                "has_merged_cells": self.has_merged_cells,
                "has_multipage_tables": self.has_multipage_tables,
                "chinese_content_ratio": self.chinese_content_ratio
            }
        }
