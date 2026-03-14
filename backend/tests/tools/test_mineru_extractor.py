"""
MinerU提取器单元测试

测试MinerUTableExtractor的核心功能：
- 初始化和可用性检测
- 表格提取（包括回退）
- HTML表格解析
- 合并单元格检测
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os

# 标记为单元测试
pytestmark = pytest.mark.unit


class TestMinerUExtractorInitialization:
    """测试MinerU提取器初始化"""

    def test_init_with_default_config(self):
        """测试使用默认配置初始化"""
        # 当MinerU未安装时，应该能够正常初始化（回退模式）
        with patch.dict('sys.modules', {'mineru': None}):
            from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor

            extractor = MinerUTableExtractor()

            assert extractor is not None
            assert extractor.mineru_config is not None
            assert extractor.mineru_config.get("enabled") == True

    def test_init_with_custom_config(self):
        """测试使用自定义配置初始化"""
        from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor

        custom_config = {
            "mineru_config": {
                "enabled": False,
                "backend": "vlm",
                "timeout_seconds": 600
            }
        }

        extractor = MinerUTableExtractor(custom_config)

        assert extractor.mineru_config.get("enabled") == False
        assert extractor.mineru_config.get("backend") == "vlm"
        assert extractor.mineru_config.get("timeout_seconds") == 600

    def test_is_available_method(self):
        """测试is_available方法"""
        from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor

        extractor = MinerUTableExtractor()

        # 应该返回布尔值
        result = extractor.is_available()
        assert isinstance(result, bool)

    def test_get_backend_info(self):
        """测试get_backend_info方法"""
        from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor

        extractor = MinerUTableExtractor()
        info = extractor.get_backend_info()

        assert isinstance(info, dict)
        assert "available" in info
        assert "backend" in info
        assert "fallback_enabled" in info


class TestMinerUExtractorFallback:
    """测试MinerU提取器的回退功能"""

    @pytest.mark.asyncio
    async def test_fallback_when_mineru_disabled(self):
        """测试当MinerU被禁用时的回退"""
        from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor

        config = {
            "mineru_config": {
                "enabled": False,
                "fallback_to_pdfplumber": True
            }
        }

        extractor = MinerUTableExtractor(config)

        # 创建一个假的PDF源
        with patch.object(extractor, '_fallback_extract') as mock_fallback:
            mock_fallback.return_value = []

            result = await extractor.extract_tables("fake.pdf")

            # 应该调用回退方法
            mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_pdfplumber(self):
        """测试回退到pdfplumber"""
        from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor

        extractor = MinerUTableExtractor()
        extractor._mineru_available = False  # 模拟MinerU不可用

        # 在_fallback_extract方法内部导入的位置进行patch
        with patch('app.tools.table_extractors.pdfplumber_extractor.PDFPlumberTableExtractor') as mock_pdfplumber:
            mock_instance = Mock()
            mock_instance.extract_tables = MagicMock(return_value=[])
            mock_pdfplumber.return_value = mock_instance

            result = await extractor._fallback_extract("fake.pdf")

            # 应该创建了pdfplumber提取器
            mock_pdfplumber.assert_called_once()


class TestHTMLTableParsing:
    """测试HTML表格解析"""

    def test_parse_simple_html_table(self):
        """测试解析简单HTML表格"""
        from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor

        extractor = MinerUTableExtractor()

        html = """
        <table>
            <tr><th>姓名</th><th>年龄</th></tr>
            <tr><td>张三</td><td>25</td></tr>
            <tr><td>李四</td><td>30</td></tr>
        </table>
        """

        rows = extractor._parse_html_table(html)

        assert len(rows) == 3
        assert rows[0] == ['姓名', '年龄']
        assert rows[1] == ['张三', '25']
        assert rows[2] == ['李四', '30']

    def test_parse_html_table_with_merged_cells(self):
        """测试解析包含合并单元格的HTML表格"""
        from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor

        extractor = MinerUTableExtractor()

        html = """
        <table>
            <tr><th colspan="2">标题</th></tr>
            <tr><td>A</td><td rowspan="2">B</td></tr>
            <tr><td>C</td></tr>
        </table>
        """

        rows = extractor._parse_html_table(html)

        assert len(rows) == 3
        assert rows[0] == ['标题']

    def test_parse_empty_html(self):
        """测试解析空HTML"""
        from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor

        extractor = MinerUTableExtractor()

        rows = extractor._parse_html_table("")
        assert rows == []

        rows = extractor._parse_html_table("<html>No table here</html>")
        assert rows == []

    def test_parse_html_simple_fallback(self):
        """测试简单HTML解析后备方法"""
        from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor

        extractor = MinerUTableExtractor()

        html = """
        <table>
            <tr><td>Cell 1</td><td>Cell 2</td></tr>
            <tr><td>Cell 3</td><td>Cell 4</td></tr>
        </table>
        """

        rows = extractor._parse_html_simple(html)

        assert len(rows) == 2
        assert 'Cell 1' in rows[0]


class TestMergedCellDetection:
    """测试合并单元格检测"""

    def test_detect_colspan(self):
        """测试检测colspan"""
        from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor

        extractor = MinerUTableExtractor()

        html = '<table><tr><td colspan="2">Merged</td></tr></table>'
        assert extractor._detect_merged_from_html(html) == True

    def test_detect_rowspan(self):
        """测试检测rowspan"""
        from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor

        extractor = MinerUTableExtractor()

        html = '<table><tr><td rowspan="2">Merged</td></tr></table>'
        assert extractor._detect_merged_from_html(html) == True

    def test_no_merged_cells(self):
        """测试没有合并单元格"""
        from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor

        extractor = MinerUTableExtractor()

        html = '<table><tr><td>A</td><td>B</td></tr></table>'
        assert extractor._detect_merged_from_html(html) == False


class TestTableConversion:
    """测试表格转换"""

    def test_convert_mineru_table_with_html(self):
        """测试转换包含HTML的MinerU表格"""
        from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor
        from app.models.table_models import ParserType

        extractor = MinerUTableExtractor()

        # 模拟MinerU表格对象
        mock_table = Mock()
        mock_table.to_html.return_value = '<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>'
        mock_table.bbox = [0, 0, 100, 50]

        result = extractor._convert_mineru_table(mock_table, 0, 1)

        assert result is not None
        assert result.page_number == 1
        assert result.parser_used == ParserType.MINERU
        assert len(result.rows) == 2

    def test_convert_mineru_table_without_html(self):
        """测试转换没有HTML的MinerU表格"""
        from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor

        extractor = MinerUTableExtractor()

        mock_table = Mock()
        mock_table.to_html.return_value = None
        mock_table.html = None

        result = extractor._convert_mineru_table(mock_table, 0, 0)

        # 没有HTML内容应该返回None
        assert result is None


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
