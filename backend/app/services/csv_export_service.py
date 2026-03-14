"""
CSV导出服务 - 表格数据导出为CSV格式
"""
import pandas as pd
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from datetime import datetime
import json

from app.models.table_models import ExtractedTable
from app.shared.config import CSV_EXPORT_CONFIG
from app.shared.logging import get_logger

logger = get_logger(__name__)


class CSVExportService:
    """
    CSV导出服务

    将提取的表格数据导出为CSV格式，
    支持UTF-8 BOM编码以确保Excel兼容性
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化CSV导出服务

        Args:
            config: 配置参数
        """
        self.config = config or CSV_EXPORT_CONFIG
        self.encoding = self.config.get("encoding", "utf-8-sig")
        self.delimiter = self.config.get("delimiter", ",")
        self.quotechar = self.config.get("quotechar", '"')
        self.include_metadata = self.config.get("include_metadata", True)
        self.include_headers = self.config.get("include_headers", True)
        self.date_format = self.config.get("date_format", "%Y-%m-%d")
        self.max_rows_per_file = self.config.get("max_rows_per_file", 100000)

        logger.info("csv_export_service_initialized",
                   encoding=self.encoding,
                   delimiter=self.delimiter,
                   include_metadata=self.include_metadata)

    def export_table_to_csv(
        self,
        table: ExtractedTable,
        output_path: Union[str, Path],
        **kwargs
    ) -> Dict[str, Any]:
        """
        导出单个表格为CSV

        Args:
            table: 提取的表格
            output_path: 输出文件路径
            **kwargs: 额外参数

        Returns:
            导出结果信息
        """
        try:
            logger.info("csv_export_started",
                       table_id=table.table_id,
                       rows=len(table.rows),
                       columns=table.columns)

            # 转换为DataFrame
            df = self._table_to_dataframe(table)

            # 应用配置
            csv_options = {
                "encoding": self.encoding,
                "sep": self.delimiter,
                "quotechar": self.quotechar,
                "index": False,  # 不写入行索引
                "header": self.include_headers
            }

            # 应用额外参数
            csv_options.update(kwargs)

            # 写入CSV文件
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            df.to_csv(output_path, **csv_options)

            # 生成结果信息
            result = {
                "table_id": table.table_id,
                "filename": output_path.name,
                "filepath": str(output_path),
                "rows": len(df),
                "columns": len(df.columns),
                "file_size_bytes": output_path.stat().st_size,
                "encoding": self.encoding,
                "exported_at": datetime.now().isoformat()
            }

            # 可选：写入元数据文件
            if self.include_metadata:
                metadata_path = output_path.with_suffix('.metadata.json')
                self._write_metadata(table, metadata_path)
                result["metadata_file"] = str(metadata_path)

            logger.info("csv_export_completed",
                       table_id=table.table_id,
                       filepath=str(output_path),
                       rows=len(df))

            return result

        except Exception as e:
            logger.error("csv_export_failed",
                        table_id=table.table_id,
                        error=str(e))
            raise

    def export_tables_to_csv(
        self,
        tables: List[ExtractedTable],
        output_dir: Union[str, Path],
        filename_prefix: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        导出多个表格为CSV

        Args:
            tables: 表格列表
            output_dir: 输出目录
            filename_prefix: 文件名前缀
            **kwargs: 额外参数

        Returns:
            导出结果摘要
        """
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            if not filename_prefix:
                filename_prefix = f"csv_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            logger.info("batch_csv_export_started",
                       table_count=len(tables),
                       output_dir=str(output_dir),
                       prefix=filename_prefix)

            export_results = []

            for idx, table in enumerate(tables):
                # 生成文件名
                filename = f"{filename_prefix}_table_{idx + 1}.csv"
                output_path = output_dir / filename

                # 导出单个表格
                result = self.export_table_to_csv(table, output_path, **kwargs)
                export_results.append(result)

            # 创建导出清单
            manifest_path = output_dir / f"{filename_prefix}_manifest.json"
            manifest = {
                "export_id": filename_prefix,
                "exported_at": datetime.now().isoformat(),
                "total_tables": len(tables),
                "total_rows": sum(r["rows"] for r in export_results),
                "encoding": self.encoding,
                "files": export_results
            }

            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            # 生成摘要
            summary = {
                "export_id": filename_prefix,
                "output_dir": str(output_dir),
                "total_tables": len(tables),
                "total_rows": sum(r["rows"] for r in export_results),
                "total_files": len(export_results),
                "manifest_file": str(manifest_path),
                "files": export_results,
                "encoding": self.encoding
            }

            logger.info("batch_csv_export_completed",
                       total_tables=len(tables),
                       total_rows=summary["total_rows"],
                       manifest=str(manifest_path))

            return summary

        except Exception as e:
            logger.error("batch_csv_export_failed", error=str(e))
            raise

    def _table_to_dataframe(self, table: ExtractedTable) -> pd.DataFrame:
        """
        将ExtractedTable转换为pandas DataFrame

        Args:
            table: 提取的表格

        Returns:
            DataFrame
        """
        if not table.rows:
            return pd.DataFrame()

        # 使用表头作为列名
        if table.headers and self.include_headers:
            columns = [str(h) if h else f"Column_{i}" for i, h in enumerate(table.headers)]
            df = pd.DataFrame(table.data_rows or [], columns=columns)
        else:
            df = pd.DataFrame(table.rows)

        # 清理数据
        df = self._clean_dataframe(df)

        # 检查是否需要分割大表
        if len(df) > self.max_rows_per_file:
            logger.warning("large_table_detected",
                          table_id=table.table_id,
                          rows=len(df),
                          max_rows=self.max_rows_per_file)

        return df

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清理DataFrame数据

        Args:
            df: 原始DataFrame

        Returns:
            清理后的DataFrame
        """
        # 移除完全空的行
        df = df.dropna(how='all')

        # 移除完全空的列
        df = df.dropna(axis=1, how='all')

        # 将None转换为空字符串
        df = df.fillna('')

        # 清理字符串单元格（去除首尾空格）
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].apply(lambda x: str(x).strip() if x else '')

        return df

    def _write_metadata(
        self,
        table: ExtractedTable,
        metadata_path: Path
    ) -> None:
        """
        写入表格元数据

        Args:
            table: 表格
            metadata_path: 元数据文件路径
        """
        try:
            metadata = {
                "table_id": table.table_id,
                "page_number": table.page_number,
                "bbox": list(table.bbox),
                "confidence_score": table.confidence_score,
                "extraction_method": table.extraction_method,
                "parser_used": table.parser_used.value,
                "table_type": table.table_type.value,
                "metadata": {
                    "has_merged_cells": table.metadata.has_merged_cells,
                    "is_continuation": table.metadata.is_continuation,
                    "has_border": table.metadata.has_border,
                    "is_rotated": table.metadata.is_rotated
                },
                "exported_at": datetime.now().isoformat(),
                "encoding": self.encoding
            }

            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            logger.debug("metadata_written",
                        table_id=table.table_id,
                        path=str(metadata_path))

        except Exception as e:
            logger.warning("metadata_write_failed",
                          table_id=table.table_id,
                          error=str(e))

    def export_to_csv_streaming(
        self,
        tables: List[ExtractedTable],
        output_path: Union[str, Path]
    ) -> None:
        """
        流式导出大量表格到单个CSV文件

        Args:
            tables: 表格列表
            output_path: 输出文件路径
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info("streaming_csv_export_started",
                       table_count=len(tables),
                       output_path=str(output_path))

            with open(output_path, 'w', encoding=self.encoding) as f:
                # 写入BOM（UTF-8-sig编码会自动处理）
                # 写入第一个表头
                first_table = True

                for table in tables:
                    df = self._table_to_dataframe(table)

                    if first_table:
                        # 写入表头
                        df.to_csv(f, index=False, sep=self.delimiter, quotechar=self.quotechar)
                        first_table = False
                    else:
                        # 不写入表头，只追加数据
                        df.to_csv(f, index=False, sep=self.delimiter, quotechar=self.quotechar, header=False)

            logger.info("streaming_csv_export_completed",
                       output_path=str(output_path),
                       file_size=output_path.stat().st_size)

        except Exception as e:
            logger.error("streaming_csv_export_failed", error=str(e))
            raise

    def export_tables(
        self,
        tables: List[ExtractedTable],
        output_dir: Union[str, Path],
        format: str = "csv",
        **kwargs
    ) -> Dict[str, Any]:
        """
        统一导出接口，支持CSV和Excel格式

        Args:
            tables: 表格列表
            output_dir: 输出目录或文件路径
            format: 导出格式 ("csv" 或 "excel")
            **kwargs: 额外参数
                - group_by_page: 是否按页分组（仅Excel）
                - filename_prefix: 文件名前缀
                - include_metadata: 是否包含元数据

        Returns:
            导出结果信息
        """
        format = format.lower()

        if format == "excel" or format == "xlsx":
            return self._export_to_excel(tables, output_dir, **kwargs)
        else:
            return self.export_tables_to_csv(tables, output_dir, **kwargs)

    def _export_to_excel(
        self,
        tables: List[ExtractedTable],
        output_dir: Union[str, Path],
        **kwargs
    ) -> Dict[str, Any]:
        """
        导出为Excel格式（委托给ExcelExportService）

        Args:
            tables: 表格列表
            output_dir: 输出目录
            **kwargs: 额外参数

        Returns:
            导出结果信息
        """
        try:
            from app.services.excel_export_service import ExcelExportService

            # 创建Excel导出服务
            excel_config = {
                "include_metadata": kwargs.get("include_metadata", self.include_metadata)
            }
            excel_service = ExcelExportService(excel_config)

            # 确定输出路径
            output_dir = Path(output_dir)
            filename_prefix = kwargs.get("filename_prefix", f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

            if output_dir.suffix == '.xlsx':
                # 如果是完整文件路径
                output_path = output_dir
            else:
                # 如果是目录，生成文件名
                output_path = output_dir / f"{filename_prefix}.xlsx"

            # 执行导出
            group_by_page = kwargs.get("group_by_page", True)
            result = excel_service.export_tables_to_excel(tables, output_path, group_by_page=group_by_page)

            logger.info("excel_export_via_csv_service",
                       filepath=result.get("filepath"),
                       sheets=result.get("sheets_created"))

            return result

        except ImportError as e:
            logger.error("excel_service_not_available", error=str(e))
            raise ImportError(
                "Excel导出需要安装openpyxl: pip install openpyxl"
            )
        except Exception as e:
            logger.error("excel_export_failed", error=str(e))
            raise

    def get_supported_formats(self) -> List[str]:
        """
        获取支持的导出格式

        Returns:
            支持的格式列表
        """
        formats = ["csv"]

        try:
            import openpyxl
            formats.append("excel")
            formats.append("xlsx")
        except ImportError:
            pass

        return formats