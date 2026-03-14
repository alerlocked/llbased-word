"""
机械加工PDF表格提取器

从机械加工工艺PDF中提取表格数据，支持电缆装配和机械加工等多种工艺文档类型。
"""

import json
from typing import Dict, List, Any, Optional
from pathlib import Path

from app.shared.logging import get_logger
from app.tools.pdf_parser import PDFParser

logger = get_logger(__name__)


def extract_mechanical_process_pdf(pdf_path: str, output_format: str = "json") -> str:
    """
    从机械加工PDF提取表格数据

    Args:
        pdf_path: PDF文件路径
        output_format: 输出格式 (json)

    Returns:
        JSON字符串格式的提取结果
    """
    try:
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        # 使用PDF解析器
        parser = PDFParser({
            "extract_tables": True,
            "extract_text": True,
            "preferred_parser": "auto"
        })

        # 执行解析
        result = parser.parse_sync(pdf_path)

        # 组织提取结果
        extraction_result = {
            "metadata": {
                "source_file": pdf_path,
                "file_name": pdf_file.name,
                "page_count": result.get("page_count", 0),
                "total_tables": len(result.get("tables", [])),
                "extraction_timestamp": _get_timestamp()
            },
            "process_cards": [],
            "operation_cards": [],
            "tool_lists": [],
            "parameter_tables": [],
            "process_flow": [],
            "quality_requirements": [],
            "raw_tables": result.get("tables", []),
            "raw_text": result.get("text", "")
        }

        # 分类表格
        tables = result.get("tables", [])
        for i, table in enumerate(tables):
            table_data = _classify_table(table, i)
            table_type = table_data.get("type", "parameter_tables")
            if table_type in extraction_result:
                extraction_result[table_type].append(table_data)

        logger.info("process_document_extracted",
                   source=pdf_path,
                   total_tables=extraction_result["metadata"]["total_tables"])

        return json.dumps(extraction_result, ensure_ascii=False, indent=2)


    except Exception as e:
        logger.exception("extract_process_document_failed", error=str(e), source=pdf_path)
        raise


def _classify_table(table: Dict[str, Any], index: int) -> Dict[str, Any]:
    """
    根据表格内容分类表格类型

    Args:
        table: 表格数据
        index: 表格索引

    Returns:
        带类型标记的表格数据
    """
    table_data = {
        "table_id": f"table_{index}",
        "type": "parameter_tables",
        "data": table,
        "page_number": table.get("page_number", 0),
        "rows": table.get("rows", []),
        "headers": table.get("headers", [])
    }

    # 根据表头关键词判断表格类型
    headers = table.get("headers", [])
    if not headers and table.get("rows"):
        # 如果没有明确表头，尝试从第一行获取
        rows = table.get("rows", [])
        if rows:
            headers = rows[0] if rows else []

    header_text = " ".join(str(h).lower() for h in headers if h)

    # 工序卡片特征
    if any(kw in header_text for kw in ["工序", "工步", "工序号", "工步号"]):
        table_data["type"] = "process_cards"
    # 操作卡片特征
    elif any(kw in header_text for kw in ["操作", "操作者", "操作说明"]):
        table_data["type"] = "operation_cards"
    # 工具清单特征
    elif any(kw in header_text for kw in ["工具", "量具", "夹具", "刀具", "设备"]):
        table_data["type"] = "tool_lists"

    return table_data


    def _get_timestamp() -> str:
    """获取当前时间戳"""
    from datetime import datetime
    return datetime.now().isoformat()
