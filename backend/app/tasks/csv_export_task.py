"""
CSV导出Celery任务 - 批量处理多个PDF文档的CSV导出
"""
from celery import Celery
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime

from app.services.csv_export_service import CSVExportService
from app.tools.process_document_extractor import extract_process_document
from app.models.table_models import ExtractedTable
from app.shared.logging import get_logger

logger = get_logger(__name__)

# 初始化Celery应用
# 注意：实际使用时需要配置Redis或RabbitMQ
celery_app = Celery('csv_export_tasks')


@celery_app.task(bind=True)
def batch_csv_export(
    self,
    doc_ids: List[str],
    export_config: Optional[Dict[str, Any]] = None,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    批量CSV导出任务

    Args:
        self: Celery任务对象
        doc_ids: 文档ID列表
        export_config: 导出配置
        output_dir: 输出目录

    Returns:
        任务结果
    """
    try:
        logger.info("batch_csv_export_started",
                   task_id=self.request.id,
                   doc_count=len(doc_ids))

        # 设置默认配置
        if export_config is None:
            export_config = {}

        # 设置输出目录
        if output_dir is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = f"data/batch_csv_exports/batch_{timestamp}"

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 创建CSV导出服务
        csv_service = CSVExportService(export_config)

        # 处理每个文档
        results = []
        processed_count = 0

        for idx, doc_id in enumerate(doc_ids):
            try:
                # 更新任务进度
                progress = (idx + 1) / len(doc_ids) * 100
                self.update_state(
                    state='PROGRESS',
                    meta={'current': idx + 1, 'total': len(doc_ids), 'progress': progress}
                )

                # 提取文档内容
                pdf_path = f"data/process_docs/{doc_id}.pdf"
                extracted_data = extract_process_document(pdf_path)

                # 转换为ExtractedTable对象
                tables = _extract_tables_from_data(extracted_data, doc_id)

                if not tables:
                    logger.warning("no_tables_found_in_doc", doc_id=doc_id)
                    continue

                # 导出为CSV
                doc_export_dir = output_path / doc_id
                doc_result = csv_service.export_tables_to_csv(
                    tables=tables,
                    output_dir=doc_export_dir,
                    filename_prefix=f"{doc_id}_export"
                )

                results.append({
                    "doc_id": doc_id,
                    "success": True,
                    "tables_exported": doc_result["total_tables"],
                    "rows_exported": doc_result["total_rows"],
                    "export_path": str(doc_export_dir)
                })

                processed_count += 1

                logger.info("doc_csv_exported",
                           doc_id=doc_id,
                           tables=doc_result["total_tables"],
                           rows=doc_result["total_rows"])

            except Exception as e:
                logger.error("doc_csv_export_failed",
                            doc_id=doc_id,
                            error=str(e))
                results.append({
                    "doc_id": doc_id,
                    "success": False,
                    "error": str(e)
                })

        # 创建汇总报告
        summary = {
            "task_id": self.request.id,
            "exported_at": datetime.now().isoformat(),
            "total_docs_requested": len(doc_ids),
            "total_docs_processed": processed_count,
            "successful_exports": sum(1 for r in results if r["success"]),
            "failed_exports": sum(1 for r in results if not r["success"]),
            "output_directory": str(output_path),
            "results": results
        }

        # 保存汇总报告
        summary_file = output_path / "batch_export_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        logger.info("batch_csv_export_completed",
                   task_id=self.request.id,
                   successful=summary["successful_exports"],
                   failed=summary["failed_exports"])

        return summary

    except Exception as e:
        logger.error("batch_csv_export_failed",
                    task_id=self.request.id,
                    error=str(e))
        raise


@celery_app.task
def export_single_doc_to_csv(
    doc_id: str,
    export_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    单个文档CSV导出任务（用于异步处理）

    Args:
        doc_id: 文档ID
        export_config: 导出配置

    Returns:
        导出结果
    """
    try:
        logger.info("single_doc_csv_export_started", doc_id=doc_id)

        # 提取文档
        pdf_path = f"data/process_docs/{doc_id}.pdf"
        extracted_data = extract_process_document(pdf_path)

        # 转换表格
        tables = _extract_tables_from_data(extracted_data, doc_id)

        if not tables:
            raise ValueError(f"No tables found in document: {doc_id}")

        # 导出CSV
        csv_service = CSVExportService(export_config or {})
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_dir = f"data/csv_exports/{doc_id}_{timestamp}"
        result = csv_service.export_tables_to_csv(
            tables=tables,
            output_dir=export_dir,
            filename_prefix=f"{doc_id}_export"
        )

        logger.info("single_doc_csv_export_completed", doc_id=doc_id)
        return result

    except Exception as e:
        logger.error("single_doc_csv_export_failed",
                    doc_id=doc_id,
                    error=str(e))
        raise


def _extract_tables_from_data(
    extracted_data: Dict[str, Any],
    doc_id: str
) -> List[ExtractedTable]:
    """
    从提取的数据中提取表格

    Args:
        extracted_data: 提取的数据
        doc_id: 文档ID

    Returns:
        表格列表
    """
    tables = []
    table_types = ["process_cards", "operation_cards", "tool_lists", "parameter_tables"]

    for table_type in table_types:
        type_tables = extracted_data.get(table_type, [])
        for table_data in type_tables:
            try:
                # 确保table_data包含必要的字段
                if isinstance(table_data, dict):
                    table = ExtractedTable.from_dict(table_data)
                    tables.append(table)
            except Exception as e:
                logger.warning("table_conversion_failed_in_batch",
                             doc_id=doc_id,
                             table_type=table_type,
                             error=str(e))
                continue

    return tables


# 任务状态检查函数
def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    获取任务状态

    Args:
        task_id: 任务ID

    Returns:
        任务状态信息
    """
    try:
        task = batch_csv_export.AsyncResult(task_id)
        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'status': 'Task is waiting to be processed'
            }
        elif task.state == 'PROGRESS':
            response = {
                'state': task.state,
                'current': task.info.get('current', 0),
                'total': task.info.get('total', 1),
                'progress': task.info.get('progress', 0)
            }
        elif task.state == 'SUCCESS':
            response = {
                'state': task.state,
                'result': task.result
            }
        else:  # FAILURE
            response = {
                'state': task.state,
                'error': str(task.info)
            }

        return response

    except Exception as e:
        logger.error("get_task_status_failed", task_id=task_id, error=str(e))
        return {'state': 'ERROR', 'error': str(e)}


# 任务取消函数
def cancel_task(task_id: str) -> bool:
    """
    取消任务

    Args:
        task_id: 任务ID

    Returns:
        是否成功取消
    """
    try:
        task = batch_csv_export.AsyncResult(task_id)
        task.revoke(terminate=True)
        logger.info("task_cancelled", task_id=task_id)
        return True
    except Exception as e:
        logger.error("task_cancel_failed", task_id=task_id, error=str(e))
        return False