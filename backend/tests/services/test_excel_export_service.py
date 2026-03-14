"""
Excel导出服务单元测试

测试ExcelExportService的核心功能：
- 按页分Sheet导出
- 单Sheet导出
- 表格数据提取
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os

# 标记为单元测试
pytestmark = pytest.mark.unit


def _has_openpyxl():
    """检查openpyxl是否已安装"""
    try:
        import openpyxl
        return True
    except ImportError:
        return False


class MockExtractedTable:
    """模拟ExtractedTable对象"""

    def __init__(self, page_number=0, rows=None, headers=None):
        self.table_id = f"test_table_{page_number}"
        self.page_number = page_number
        self.bbox = (0, 0, 100, 50)
        self.rows = rows or [["A", "B"], ["1", "2"]]
        self.headers = headers
        self.data_rows = self.rows[1:] if len(self.rows) > 1 else []
        self.columns = len(self.rows[0]) if self.rows else 0
        self.confidence_score = 0.95
        self.extraction_method = "test"
        self.parser_used = Mock(value="test")
        self.table_type = Mock(value="general_table")
        self.metadata = Mock(
            has_merged_cells=False,
            is_continuation=False,
            has_border=True
        )

    def to_dict(self):
        return {
            "table_id": self.table_id,
            "page_number": self.page_number,
            "rows": self.rows,
            "headers": self.headers,
            "confidence_score": self.confidence_score
        }


class TestExcelExportServiceInit:
    """测试Excel导出服务初始化"""

    def test_init_with_default_config(self):
        """测试使用默认配置初始化"""
        from app.services.excel_export_service import ExcelExportService

        service = ExcelExportService()

        assert service.include_metadata == True
        assert service.sheet_name_prefix == "第"

    def test_init_with_custom_config(self):
        """测试使用自定义配置初始化"""
        from app.services.excel_export_service import ExcelExportService

        config = {
            "include_metadata": False,
            "sheet_name_prefix": "Page"
        }

        service = ExcelExportService(config)

        assert service.include_metadata == False
        assert service.sheet_name_prefix == "Page"


class TestTableDataExtraction:
    """测试表格数据提取方法"""

    def test_get_page_number_from_object(self):
        """测试从对象获取页码"""
        from app.services.excel_export_service import ExcelExportService

        service = ExcelExportService()
        table = MockExtractedTable(page_number=5)

        result = service._get_page_number(table)
        assert result == 5

    def test_get_page_number_from_dict(self):
        """测试从字典获取页码"""
        from app.services.excel_export_service import ExcelExportService

        service = ExcelExportService()
        table = {"page_number": 3}

        result = service._get_page_number(table)
        assert result == 3

    def test_get_table_rows_from_object(self):
        """测试从对象获取行数据"""
        from app.services.excel_export_service import ExcelExportService

        service = ExcelExportService()
        table = MockExtractedTable(rows=[["H1", "H2"], ["V1", "V2"]])

        result = service._get_table_rows(table)
        assert len(result) == 2
        assert result[0] == ["H1", "H2"]

    def test_get_table_rows_from_dict(self):
        """测试从字典获取行数据"""
        from app.services.excel_export_service import ExcelExportService

        service = ExcelExportService()
        table = {"rows": [["A", "B"]]}

        result = service._get_table_rows(table)
        assert result == [["A", "B"]]

    def test_get_table_headers(self):
        """测试获取表头"""
        from app.services.excel_export_service import ExcelExportService

        service = ExcelExportService()

        # 从对象获取
        table1 = MockExtractedTable(headers=["H1", "H2"])
        result1 = service._get_table_headers(table1)
        assert result1 == ["H1", "H2"]

        # 从字典获取
        table2 = {"headers": ["A", "B"]}
        result2 = service._get_table_headers(table2)
        assert result2 == ["A", "B"]

    def test_get_table_metadata(self):
        """测试获取元数据"""
        from app.services.excel_export_service import ExcelExportService

        service = ExcelExportService()
        table = MockExtractedTable()
        table.confidence_score = 0.95
        table.extraction_method = "mineru"

        result = service._get_table_metadata(table)

        assert result.get("confidence") == "0.95"
        assert result.get("method") == "mineru"


class TestExcelExport:
    """测试Excel导出功能"""

    @pytest.mark.skipif(
        not _has_openpyxl(),
        reason="openpyxl not installed"
    )
    def test_export_by_page(self):
        """测试按页导出"""
        from app.services.excel_export_service import ExcelExportService

        service = ExcelExportService()

        # 创建测试表格
        tables = [
            MockExtractedTable(page_number=0, rows=[["P1_A", "P1_B"], ["1", "2"]]),
            MockExtractedTable(page_number=1, rows=[["P2_A", "P2_B"], ["3", "4"]]),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_output.xlsx"

            result = service.export_tables_to_excel(tables, output_path, group_by_page=True)

            assert result["filepath"] == str(output_path)
            assert result["sheets_created"] == 2
            assert result["total_tables"] == 2
            assert os.path.exists(output_path)

    @pytest.mark.skipif(
        not _has_openpyxl(),
        reason="openpyxl not installed"
    )
    def test_export_single_sheet(self):
        """测试单Sheet导出"""
        from app.services.excel_export_service import ExcelExportService

        service = ExcelExportService()

        tables = [
            MockExtractedTable(page_number=0),
            MockExtractedTable(page_number=1),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_single.xlsx"

            result = service.export_tables_to_excel(tables, output_path, group_by_page=False)

            assert result["sheets_created"] == 1
            assert result["total_tables"] == 2

    @pytest.mark.skipif(
        not _has_openpyxl(),
        reason="openpyxl not installed"
    )
    def test_export_empty_tables(self):
        """测试导出空表格列表"""
        from app.services.excel_export_service import ExcelExportService

        service = ExcelExportService()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_empty.xlsx"

            result = service.export_tables_to_excel([], output_path)

            assert result["total_tables"] == 0


class TestCSVExportServiceIntegration:
    """测试CSV导出服务的Excel集成"""

    def test_get_supported_formats(self):
        """测试获取支持的格式"""
        from app.services.csv_export_service import CSVExportService

        service = CSVExportService()
        formats = service.get_supported_formats()

        assert "csv" in formats
        # openpyxl可能安装也可能没安装
        assert isinstance(formats, list)

    def test_export_tables_csv_format(self):
        """测试CSV格式导出"""
        from app.services.csv_export_service import CSVExportService

        service = CSVExportService()

        tables = [MockExtractedTable()]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(service, 'export_tables_to_csv') as mock_csv:
                mock_csv.return_value = {"format": "csv"}

                result = service.export_tables(tables, tmpdir, format="csv")

                mock_csv.assert_called_once()


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
