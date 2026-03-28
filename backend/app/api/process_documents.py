"""
工艺文档API - 提供工艺文件查看和管理接口
支持CSV导出功能
"""
from fastapi import APIRouter, HTTPException, Query, Response
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import os
from datetime import datetime

from app.tools.process_document_extractor import extract_process_document
from app.services.csv_export_service import CSVExportService
from app.models.table_models import ExtractedTable
from app.shared.logging import get_logger
from app.config import settings

logger = get_logger(__name__)

router = APIRouter(prefix="/api/process-documents", tags=["process-documents"])

# 数据路径配置 - 使用统一的配置
PROCESS_DOCS_PATH = settings.DATA_DIR / "process_docs"
EXTRACTED_PATH = settings.DATA_DIR / "extracted"


@router.get("/")
async def list_process_documents():
    """
    列出所有工艺文档
    """
    try:
        if not PROCESS_DOCS_PATH.exists():
            return {"documents": [], "count": 0}

        documents = []
        for pdf_file in PROCESS_DOCS_PATH.glob("*.pdf"):
            # 检查是否有对应的提取结果
            extracted_file = EXTRACTED_PATH / f"{pdf_file.stem}_extraction_result.json"
            has_extracted = extracted_file.exists()

            documents.append({
                "id": pdf_file.stem,
                "name": pdf_file.name,
                "path": str(pdf_file.relative_to(PROJECT_ROOT)),
                "size": pdf_file.stat().st_size,
                "created_at": pdf_file.stat().st_ctime,
                "has_extracted": has_extracted,
                "extracted_path": str(extracted_file) if has_extracted else None
            })

        # 按创建时间排序
        documents.sort(key=lambda x: x["created_at"], reverse=True)

        logger.info("process_documents_listed", count=len(documents))
        return {"documents": documents, "count": len(documents)}

    except Exception as e:
        logger.exception("list_process_documents_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"列出工艺文档失败: {str(e)}")


@router.get("/{doc_id}/extracted")
async def get_extracted_content(doc_id: str):
    """
    获取工艺文档的提取内容
    """
    try:
        extracted_file = EXTRACTED_PATH / f"{doc_id}_extraction_result.json"

        if not extracted_file.exists():
            # 如果没有提取结果，实时提取
            pdf_file = PROCESS_DOCS_PATH / f"{doc_id}.pdf"
            if not pdf_file.exists():
                raise HTTPException(status_code=404, detail=f"工艺文档不存在: {doc_id}")

            # 执行提取
            result = extract_process_document(str(pdf_file))

            # 保存提取结果
            EXTRACTED_PATH.mkdir(parents=True, exist_ok=True)
            with open(extracted_file, 'w', encoding='utf-8') as f:
                f.write(result)

            logger.info("process_document_extracted", doc_id=doc_id)

        # 读取提取结果
        with open(extracted_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        logger.info("extracted_content_retrieved", doc_id=doc_id)
        return data

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_extracted_content_failed", doc_id=doc_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"获取提取内容失败: {str(e)}")


@router.post("/{doc_id}/extract")
async def extract_document(doc_id: str):
    """
    重新提取工艺文档内容
    """
    try:
        pdf_file = PROCESS_DOCS_PATH / f"{doc_id}.pdf"

        if not pdf_file.exists():
            raise HTTPException(status_code=404, detail=f"工艺文档不存在: {doc_id}")

        # 执行提取
        result = extract_process_document(str(pdf_file))

        # 保存提取结果
        extracted_file = EXTRACTED_PATH / f"{doc_id}_extraction_result.json"
        EXTRACTED_PATH.mkdir(parents=True, exist_ok=True)
        with open(extracted_file, 'w', encoding='utf-8') as f:
            f.write(result)

        logger.info("process_document_re_extracted", doc_id=doc_id)

        # 返回提取结果
        return json.loads(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("extract_document_failed", doc_id=doc_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"提取文档失败: {str(e)}")


@router.get("/{doc_id}/summary")
async def get_document_summary(doc_id: str):
    """
    获取工艺文档摘要
    """
    try:
        data = await get_extracted_content(doc_id)

        # 生成摘要
        summary = {
            "doc_id": doc_id,
            "total_tables": data.get("metadata", {}).get("total_tables", 0),
            "by_type": {
                "process_cards": len(data.get("process_cards", [])),
                "operation_cards": len(data.get("operation_cards", [])),
                "tool_lists": len(data.get("tool_lists", [])),
                "parameter_tables": len(data.get("parameter_tables", []))
            },
            "process_steps_count": len(data.get("metadata", {}).get("process_steps", [])),
            "page_count": data.get("metadata", {}).get("page_count", 0),
            "extraction_timestamp": data.get("metadata", {}).get("extraction_timestamp", "")
        }

        logger.info("document_summary_generated", doc_id=doc_id)
        return summary

    except Exception as e:
        logger.exception("get_document_summary_failed", doc_id=doc_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"生成摘要失败: {str(e)}")


@router.get("/{doc_id}/tables/{table_type}")
async def get_tables_by_type(doc_id: str, table_type: str):
    """
    获取特定类型的表格

    Args:
        table_type: 表格类型 (process_cards, operation_cards, tool_lists, parameter_tables)
    """
    try:
        data = await get_extracted_content(doc_id)

        if table_type not in ["process_cards", "operation_cards", "tool_lists", "parameter_tables"]:
            raise HTTPException(status_code=400, detail=f"无效的表格类型: {table_type}")

        tables = data.get(table_type, [])

        # 添加表格类型信息
        result = {
            "doc_id": doc_id,
            "table_type": table_type,
            "count": len(tables),
            "tables": tables
        }

        logger.info("tables_by_type_retrieved", doc_id=doc_id, table_type=table_type, count=len(tables))
        return result

    except Exception as e:
        logger.exception("get_tables_by_type_failed", doc_id=doc_id, table_type=table_type, error=str(e))
        raise HTTPException(status_code=500, detail=f"获取表格失败: {str(e)}")


@router.get("/{doc_id}/tools")
async def get_tool_list(doc_id: str):
    """
    获取工具清单（简化版，便于前端展示）
    """
    try:
        data = await get_extracted_content(doc_id)
        tool_lists = data.get("tool_lists", [])

        # 简化工具清单格式
        simplified_tools = []
        for tool_list in tool_lists:
            for row in tool_list.get("rows", []):
                if row.get("cells"):
                    # 提取工具名称和规格
                    cells = row["cells"]
                    if len(cells) >= 2:
                        simplified_tools.append({
                            "name": cells[0],
                            "specification": cells[1] if len(cells) > 1 else "",
                            "page": tool_list.get("page_number", 0),
                            "row_index": tool_list["rows"].index(row)
                        })

        logger.info("tool_list_retrieved", doc_id=doc_id, tool_count=len(simplified_tools))
        return {
            "doc_id": doc_id,
            "tools": simplified_tools,
            "total": len(simplified_tools)
        }

    except Exception as e:
        logger.exception("get_tool_list_failed", doc_id=doc_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"获取工具清单失败: {str(e)}")


@router.get("/{doc_id}/view")
async def get_document_view_data(doc_id: str):
    """
    获取文档查看所需的所有数据（用于前端完整展示）
    """
    try:
        data = await get_extracted_content(doc_id)

        # 组织数据便于前端展示
        view_data = {
            "doc_id": doc_id,
            "metadata": data.get("metadata", {}),
            "summary": {
                "total_tables": data.get("metadata", {}).get("total_tables", 0),
                "by_type": {
                    "process_cards": len(data.get("process_cards", [])),
                    "operation_cards": len(data.get("operation_cards", [])),
                    "tool_lists": len(data.get("tool_lists", [])),
                    "parameter_tables": len(data.get("parameter_tables", []))
                }
            },
            "content": {
                "process_cards": data.get("process_cards", []),
                "operation_cards": data.get("operation_cards", []),
                "tool_lists": data.get("tool_lists", []),
                "parameter_tables": data.get("parameter_tables", []),
                "process_flow": data.get("process_flow", []),
                "quality_requirements": data.get("quality_requirements", [])
            },
            "process_steps": data.get("metadata", {}).get("process_steps", [])
        }

        logger.info("document_view_data_generated", doc_id=doc_id)
        return view_data

    except Exception as e:
        logger.exception("get_document_view_data_failed", doc_id=doc_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"获取查看数据失败: {str(e)}")


@router.delete("/{doc_id}/extracted")
async def delete_extracted_content(doc_id: str):
    """
    删除提取的内容（用于重新提取）
    """
    try:
        extracted_file = EXTRACTED_PATH / f"{doc_id}_extraction_result.json"

        if extracted_file.exists():
            extracted_file.unlink()
            logger.info("extracted_content_deleted", doc_id=doc_id)
            return {"message": f"已删除提取内容: {doc_id}"}
        else:
            return {"message": f"提取内容不存在: {doc_id}"}

    except Exception as e:
        logger.exception("delete_extracted_content_failed", doc_id=doc_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# CSV导出相关端点

@router.post("/{doc_id}/export-csv")
async def export_to_csv(
    doc_id: str,
    table_ids: Optional[List[str]] = None,
    include_metadata: bool = True,
    merge_multipage: bool = True
):
    """
    导出表格为CSV格式

    Args:
        doc_id: 文档ID
        table_ids: 要导出的表格ID列表（可选，默认全部）
        include_metadata: 是否包含元数据
        merge_multipage: 是否合并跨页表格
    """
    try:
        # 获取提取的内容
        data = await get_extracted_content(doc_id)

        # 提取表格数据
        tables = []
        table_types = ["process_cards", "operation_cards", "tool_lists", "parameter_tables"]

        for table_type in table_types:
            type_tables = data.get(table_type, [])
            for table_data in type_tables:
                # 转换为ExtractedTable对象
                try:
                    table = ExtractedTable.from_dict(table_data)
                    tables.append(table)
                except Exception as e:
                    logger.warning("table_conversion_failed",
                                 table_type=table_type,
                                 error=str(e))
                    continue

        if not tables:
            raise HTTPException(status_code=404, detail="未找到可导出的表格")

        # 过滤指定的表格ID
        if table_ids:
            tables = [t for t in tables if t.table_id in table_ids]
            if not tables:
                raise HTTPException(status_code=404, detail="未找到指定的表格ID")

        # 合并跨页表格
        if merge_multipage and len(tables) > 1:
            from app.tools.table_merger import TableMerger
            merger = TableMerger()
            tables = merger.detect_and_merge_tables(tables)

        # 创建CSV导出服务
        csv_service = CSVExportService({
            "include_metadata": include_metadata
        })

        # 生成导出ID
        export_id = f"csv_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{doc_id}"
        export_dir = settings.CSV_EXPORTS_DIR / export_id
        export_dir.mkdir(parents=True, exist_ok=True)

        # 执行导出
        result = csv_service.export_tables_to_csv(
            tables=tables,
            output_dir=export_dir,
            filename_prefix=export_id
        )

        # 返回结果
        response = {
            "export_id": export_id,
            "doc_id": doc_id,
            "total_tables": result["total_tables"],
            "total_rows": result["total_rows"],
            "files": result["files"],
            "download_url": f"/api/process-documents/{doc_id}/csv/{export_id}",
            "manifest_file": result["manifest_file"]
        }

        logger.info("csv_export_api_completed",
                   doc_id=doc_id,
                   export_id=export_id,
                   total_tables=result["total_tables"])

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("csv_export_api_failed", doc_id=doc_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"CSV导出失败: {str(e)}")


@router.get("/{doc_id}/csv/{export_id}")
async def download_csv_export(
    doc_id: str,
    export_id: str,
    filename: Optional[str] = None
):
    """
    下载CSV导出文件

    Args:
        doc_id: 文档ID
        export_id: 导出ID
        filename: 具体文件名（可选，默认下载所有文件的ZIP包）
    """
    try:
        export_dir = settings.CSV_EXPORTS_DIR / export_id

        if not export_dir.exists():
            raise HTTPException(status_code=404, detail="导出文件不存在")

        if filename:
            # 下载单个CSV文件
            file_path = export_dir / filename
            if not file_path.exists() or not file_path.suffix.lower() == '.csv':
                raise HTTPException(status_code=404, detail="CSV文件不存在")

            # 读取文件内容
            with open(file_path, 'rb') as f:
                content = f.read()

            # 设置响应头
            headers = {
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "text/csv; charset=utf-8"
            }

            logger.info("csv_file_downloaded",
                       doc_id=doc_id,
                       export_id=export_id,
                       filename=filename)

            return Response(content=content, headers=headers)

        else:
            # 下载所有文件（需要创建ZIP包）
            import zipfile
            from io import BytesIO

            zip_buffer = BytesIO()

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in export_dir.glob("*.csv"):
                    zip_file.write(file_path, file_path.name)

                # 添加清单文件
                manifest_path = export_dir / f"{export_id}_manifest.json"
                if manifest_path.exists():
                    zip_file.write(manifest_path, manifest_path.name)

            zip_buffer.seek(0)
            zip_content = zip_buffer.getvalue()

            headers = {
                "Content-Disposition": f'attachment; filename="{export_id}.zip"',
                "Content-Type": "application/zip"
            }

            logger.info("csv_zip_downloaded",
                       doc_id=doc_id,
                       export_id=export_id,
                       file_count=len(list(export_dir.glob("*.csv"))))

            return Response(content=zip_content, headers=headers)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("csv_download_failed",
                        doc_id=doc_id,
                        export_id=export_id,
                        error=str(e))
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


@router.get("/{doc_id}/csv-config")
async def get_csv_config():
    """
    获取CSV导出配置
    """
    try:
        from app.shared.config import CSV_EXPORT_CONFIG
        return CSV_EXPORT_CONFIG

    except Exception as e:
        logger.exception("get_csv_config_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.get("/{doc_id}/parser-config")
async def get_parser_config(doc_id: str):
    """
    获取解析器配置和文档分析结果
    """
    try:
        from app.tools.parser_selector import ParserSelector
        from app.shared.config import PDF_PARSER_CONFIG

        pdf_file = PROCESS_DOCS_PATH / f"{doc_id}.pdf"
        if not pdf_file.exists():
            raise HTTPException(status_code=404, detail=f"工艺文档不存在: {doc_id}")

        # 分析文档
        selector = ParserSelector(PDF_PARSER_CONFIG)
        analysis_result = await selector.select_parser(str(pdf_file))

        response = {
            "recommended_parser": analysis_result.selected_parser.value,
            "complexity_score": analysis_result.complexity_score,
            "reasoning": analysis_result.reasoning,
            "analysis_details": {
                "table_count": analysis_result.table_count,
                "has_borderless_tables": analysis_result.has_borderless_tables,
                "has_merged_cells": analysis_result.has_merged_cells,
                "has_multipage_tables": analysis_result.has_multipage_tables,
                "chinese_content_ratio": analysis_result.chinese_content_ratio
            },
            "config": PDF_PARSER_CONFIG
        }

        logger.info("parser_config_retrieved", doc_id=doc_id)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_parser_config_failed", doc_id=doc_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"获取解析器配置失败: {str(e)}")