"""
PDFPlumber提取器单元测试
"""
import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch

from app.tools.table_extractors.pdfplumber_extractor import PDFPlumberTableExtractor
from app.models.table_models import ExtractedTable, ParserType


class TestPDFPlumberTableExtractor:
    """PDFPlumber表格提取器测试"""

    @pytest.fixture
    def extractor(self):
        """创建提取器实例"""
        config = {
            "table_settings": {
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "snap_tolerance": 3,
                "join_tolerance": 3
            }
        }
        return PDFPlumberTableExtractor(config)

    @pytest.fixture
    def test_pdf_path(self):
        """测试PDF文件路径"""
        # 创建一个简单的测试PDF
        test_dir = Path("backend/tests/fixtures/pdfs")
        test_dir.mkdir(parents=True, exist_ok=True)
        return str(test_dir / "simple_table.pdf")

    def test_extractor_initialization(self, extractor):
        """测试提取器初始化"""
        assert extractor is not None
        assert hasattr(extractor, 'table_settings')
        assert 'vertical_strategy' in extractor.table_settings

    @pytest.mark.unit
    def test_generate_table_id(self, extractor):
        """测试表格ID生成"""
        table_id = extractor._generate_table_id(0, 1)
        assert table_id == "table_0_1"

    @pytest.mark.unit
    def test_calculate_confidence_score(self, extractor):
        """测试置信度分数计算"""
        # 完整表格
        rows = [["Header1", "Header2"], ["Data1", "Data2"], ["Data3", "Data4"]]
        confidence = extractor._calculate_confidence_score(rows)
        assert 0.0 <= confidence <= 1.0

        # 不完整表格
        incomplete_rows = [["Header1", "Header2"], ["Data1"]]  # 第二行缺少一列
        confidence_incomplete = extractor._calculate_confidence_score(incomplete_rows)
        assert confidence_incomplete < confidence

    @pytest.mark.unit
    def test_detect_table_type(self, extractor):
        """测试表格类型检测"""
        # 工艺表格
        process_headers = ["工序", "操作步骤", "工具"]
        table_type = extractor._detect_table_type(process_headers)
        assert table_type == "process_table"

        # 材料表格
        material_headers = ["材料", "规格", "数量"]
        table_type = extractor._detect_table_type(material_headers)
        assert table_type == "material_table"

        # 质量表格
        quality_headers = ["检验项目", "标准", "结果"]
        table_type = extractor._detect_table_type(quality_headers)
        assert table_type == "quality_table"

        # 通用表格
        general_headers = ["Column1", "Column2", "Column3"]
        table_type = extractor._detect_table_type(general_headers)
        assert table_type == "general_table"

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('pdfplumber.open')
    async def test_extract_tables_from_page(self, mock_pdfplumber_open, extractor):
        """测试从页面提取表格（集成测试）"""
        # 创建模拟的pdfplumber页面和表格
        mock_table = Mock()
        mock_table.bbox = (100, 100, 500, 300)
        mock_table.extract.return_value = [["Header1", "Header2"], ["Data1", "Data2"]]

        mock_page = Mock()
        mock_page.find_tables.return_value = [mock_table]

        mock_pdf = Mock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber_open.return_value = mock_pdf

        # 执行提取
        result = await extractor._extract_tables_from_page(mock_page, 0, extractor.table_settings)

        # 验证结果
        assert len(result) == 1
        assert isinstance(result[0], ExtractedTable)
        assert result[0].parser_used == ParserType.PDFPLUMBER
        assert result[0].columns == 2
        assert len(result[0].rows) == 2

    @pytest.mark.integration
    def test_chinese_content_handling(self, extractor):
        """测试中文内容处理"""
        # 测试中文表头
        chinese_headers = ["工序名称", "操作要求", "工艺参数"]
        table_type = extractor._detect_table_type(chinese_headers)
        assert table_type in ["process_table", "general_table"]

        # 测试中文数据
        chinese_rows = [["车削", "粗加工", "转速1000"], ["铣削", "精加工", "转速800"]]
        confidence = extractor._calculate_confidence_score(chinese_rows)
        assert confidence > 0.0

    @pytest.mark.unit
    def test_optimize_settings_for_chinese(self, extractor):
        """测试中文优化设置"""
        mock_page = Mock()
        settings = extractor.optimize_settings_for_chinese(mock_page)

        assert settings["vertical_strategy"] == "text"
        assert settings["horizontal_strategy"] == "text"
        assert settings["snap_tolerance"] == 5
        assert settings["join_tolerance"] == 5

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_handling(self, extractor):
        """测试错误处理"""
        # 测试空PDF
        with pytest.raises(Exception):
            await extractor.extract_tables("nonexistent.pdf")

        # 测试无效表格数据
        mock_page = Mock()
        mock_page.find_tables.return_value = []
        result = await extractor._extract_tables_from_page(mock_page, 0, {})
        assert result == []

    @pytest.mark.performance
    def test_large_table_performance(self, extractor):
        """测试大表格性能"""
        # 创建大表格数据
        large_rows = []
        for i in range(1000):
            large_rows.append([f"Cell_{i}_{j}" for j in range(10)])

        import time
        start_time = time.time()
        confidence = extractor._calculate_confidence_score(large_rows)
        end_time = time.time()

        # 确保计算在合理时间内完成
        assert end_time - start_time < 5.0  # 5秒内
        assert 0.0 <= confidence <= 1.0
