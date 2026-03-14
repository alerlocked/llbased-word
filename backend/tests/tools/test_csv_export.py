"""
CSV导出功能测试
"""
import pytest
import pandas as pd
from pathlib import Path
import json
from unittest.mock import Mock, patch

from app.services.csv_export_service import CSVExportService
from app.models.table_models import ExtractedTable, TableMetadata, ParserType, TableType


class TestCSVExportService:
    """CSV导出服务测试"""

    @pytest.fixture
    def csv_service(self):
        """创建CSV导出服务实例"""
        config = {
            "encoding": "utf-8-sig",
            "delimiter": ",",
            "include_metadata": True,
            "include_headers": True
        }
        return CSVExportService(config)

    @pytest.fixture
    def sample_table(self):
        """创建示例表格"""
        metadata = TableMetadata(
            has_merged_cells=False,
            is_continuation=False,
            has_border=True,
            is_rotated=False,
            confidence_score=0.95
        )

        return ExtractedTable(
            table_id="test_table_1",
            page_number=0,
            bbox=(100, 100, 500, 300),
            rows=[["姓名", "年龄", "城市"], ["张三", "25", "北京"], ["李四", "30", "上海"]],
            columns=3,
            headers=["姓名", "年龄", "城市"],
            data_rows=[["张三", "25", "北京"], ["李四", "30", "上海"]],
            confidence_score=0.95,
            extraction_method="pdfplumber",
            parser_used=ParserType.PDFPLUMBER,
            metadata=metadata,
            table_type=TableType.GENERAL_TABLE
        )

    @pytest.fixture
    def test_output_dir(self):
        """测试输出目录"""
        output_dir = Path("backend/tests/fixtures/exports")
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    @pytest.mark.unit
    def test_service_initialization(self, csv_service):
        """测试服务初始化"""
        assert csv_service.encoding == "utf-8-sig"
        assert csv_service.delimiter == ","
        assert csv_service.include_metadata is True

    @pytest.mark.unit
    def test_table_to_dataframe(self, csv_service, sample_table):
        """测试表格转DataFrame"""
        df = csv_service._table_to_dataframe(sample_table)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2  # 数据行数
        assert len(df.columns) == 3  # 列数
        assert list(df.columns) == ["姓名", "年龄", "城市"]

    @pytest.mark.integration
    def test_export_single_table(self, csv_service, sample_table, test_output_dir):
        """测试单个表格导出"""
        output_path = test_output_dir / "test_single_table.csv"

        result = csv_service.export_table_to_csv(sample_table, output_path)

        # 验证结果
        assert result["table_id"] == "test_table_1"
        assert result["filename"] == "test_single_table.csv"
        assert result["rows"] == 2
        assert result["columns"] == 3
        assert result["encoding"] == "utf-8-sig"

        # 验证文件存在
        assert output_path.exists()

        # 验证文件内容
        with open(output_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            assert "姓名" in content
            assert "张三" in content
            assert "李四" in content

        # 验证元数据文件
        metadata_path = output_path.with_suffix('.metadata.json')
        assert metadata_path.exists()

        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
            assert metadata["table_id"] == "test_table_1"
            assert metadata["parser_used"] == "pdfplumber"

    @pytest.mark.integration
    def test_export_multiple_tables(self, csv_service, sample_table, test_output_dir):
        """测试多个表格导出"""
        # 创建多个表格
        tables = [sample_table]
        # 添加第二个表格
        second_table = ExtractedTable(
            table_id="test_table_2",
            page_number=1,
            bbox=(100, 100, 500, 300),
            rows=[["产品", "价格", "库存"], ["手机", "5000", "100"], ["电脑", "8000", "50"]],
            columns=3,
            headers=["产品", "价格", "库存"],
            data_rows=[["手机", "5000", "100"], ["电脑", "8000", "50"]],
            confidence_score=0.90,
            extraction_method="pymupdf",
            parser_used=ParserType.PYMUPDF,
            metadata=TableMetadata(),
            table_type=TableType.GENERAL_TABLE
        )
        tables.append(second_table)

        output_dir = test_output_dir / "batch_export"
        result = csv_service.export_tables_to_csv(tables, output_dir)

        # 验证结果
        assert result["total_tables"] == 2
        assert result["total_rows"] == 4
        assert result["total_files"] == 2

        # 验证清单文件
        manifest_path = Path(result["manifest_file"])
        assert manifest_path.exists()

        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
            assert manifest["total_tables"] == 2
            assert len(manifest["files"]) == 2

    @pytest.mark.integration
    def test_chinese_character_support(self, csv_service, test_output_dir):
        """测试中文字符支持"""
        chinese_table = ExtractedTable(
            table_id="chinese_test",
            page_number=0,
            bbox=(100, 100, 500, 300),
            rows=[["工艺名称", "操作步骤", "技术要求"], ["车削加工", "粗车外圆", "表面粗糙度Ra3.2"]],
            columns=3,
            headers=["工艺名称", "操作步骤", "技术要求"],
            data_rows=[["车削加工", "粗车外圆", "表面粗糙度Ra3.2"]],
            confidence_score=0.98,
            extraction_method="hybrid",
            parser_used=ParserType.HYBRID,
            metadata=TableMetadata(),
            table_type=TableType.PROCESS_TABLE
        )

        output_path = test_output_dir / "chinese_test.csv"
        result = csv_service.export_table_to_csv(chinese_table, output_path)

        # 验证中文字符正确保存
        with open(output_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            assert "工艺名称" in content
            assert "车削加工" in content
            assert "表面粗糙度Ra3.2" in content

    @pytest.mark.unit
    def test_clean_dataframe(self, csv_service):
        """测试DataFrame清理"""
        import pandas as pd

        # 创建包含空值和空格的DataFrame
        df = pd.DataFrame({
            'A': ['  text1  ', None, 'text3'],
            'B': ['', 'text2', '  text4  '],
            'C': [None, None, 'text5']
        })

        cleaned_df = csv_service._clean_dataframe(df)

        # 验证清理结果
        assert cleaned_df.iloc[0]['A'] == 'text1'
        assert cleaned_df.iloc[0]['B'] == ''
        assert cleaned_df.iloc[0]['C'] == ''
        assert cleaned_df.iloc[1]['A'] == ''
        assert cleaned_df.iloc[1]['B'] == 'text2'
        assert cleaned_df.iloc[1]['C'] == ''

    @pytest.mark.integration
    def test_streaming_export(self, csv_service, sample_table, test_output_dir):
        """测试流式导出"""
        tables = [sample_table]
        output_path = test_output_dir / "streaming_test.csv"

        csv_service.export_to_csv_streaming(tables, output_path)

        # 验证文件存在
        assert output_path.exists()

        # 验证内容
        df = pd.read_csv(output_path, encoding='utf-8-sig')
        assert len(df) == 2
        assert list(df.columns) == ["姓名", "年龄", "城市"]

    @pytest.mark.error_handling
    def test_error_handling(self, csv_service, test_output_dir):
        """测试错误处理"""
        # 测试空表格
        empty_table = ExtractedTable(
            table_id="empty_table",
            page_number=0,
            bbox=(0, 0, 0, 0),
            rows=[],
            columns=0,
            headers=None,
            data_rows=None,
            confidence_score=0.0,
            extraction_method="test",
            parser_used=ParserType.PYMUPDF,
            metadata=TableMetadata(),
            table_type=TableType.GENERAL_TABLE
        )

        output_path = test_output_dir / "empty_test.csv"
        result = csv_service.export_table_to_csv(empty_table, output_path)

        assert result["rows"] == 0
        assert output_path.exists()

        # 测试无效路径
        with pytest.raises(Exception):
            csv_service.export_table_to_csv(sample_table, "/invalid/path/file.csv")
