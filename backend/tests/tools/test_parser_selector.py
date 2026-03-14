"""
Parser Selector Unit Tests - 双复杂度模式
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock

from app.tools.parser_selector import ParserSelector
from app.models.table_models import ParserType


class TestParserSelectorDualMode:
    """双复杂度模式测试"""

    @pytest.fixture
    def selector(self):
        """创建解析器选择器"""
        return ParserSelector()

    @pytest.mark.asyncio
    async def test_select_simple_mode_no_tables(self, selector):
        """测试无表格文档选择简单模式"""
        with patch.object(selector, 'quick_detect_tables', new_callable=AsyncMock) as mock_detect:
            mock_detect.return_value = (False, 0)

            result = await selector.select_parser("no_tables.pdf")

            assert result.selected_parser == ParserType.SIMPLE
            assert result.has_tables is False
            assert result.table_count == 0

    @pytest.mark.asyncio
    async def test_select_complex_mode_with_tables(self, selector):
        """测试有表格文档选择复杂模式"""
        with patch.object(selector, 'quick_detect_tables', new_callable=AsyncMock) as mock_detect:
            with patch.object(selector, '_mineru_available', True):
                mock_detect.return_value = (True, 3)

                result = await selector.select_parser("with_tables.pdf")

                assert result.selected_parser == ParserType.COMPLEX
                assert result.has_tables is True
                assert result.table_count == 3

    @pytest.mark.asyncio
    async def test_force_simple_mode(self, selector):
        """测试强制简单模式"""
        result = await selector.select_parser("any.pdf", force_mode="simple")
        assert result.selected_parser == ParserType.SIMPLE
        assert "强制" in result.reasoning

    @pytest.mark.asyncio
    async def test_force_complex_mode(self, selector):
        """测试强制复杂模式"""
        result = await selector.select_parser("any.pdf", force_mode="complex")
        assert result.selected_parser == ParserType.COMPLEX
        assert "强制" in result.reasoning

    @pytest.mark.asyncio
    async def test_fallback_to_simple_when_mineru_unavailable(self, selector):
        """测试MinerU不可用时回退到简单模式"""
        with patch.object(selector, 'quick_detect_tables', new_callable=AsyncMock) as mock_detect:
            with patch.object(selector, '_mineru_available', False):
                mock_detect.return_value = (True, 2)

                result = await selector.select_parser("with_tables.pdf")

                assert result.selected_parser == ParserType.SIMPLE
                assert result.has_tables is True


class TestParserSelectorBackwardCompatibility:
    """向后兼容测试"""

    def test_parser_type_aliases(self):
        """测试ParserType别名 - 旧名称映射到新模式"""
        assert ParserType.PYMUPDF == ParserType.SIMPLE
        assert ParserType.PDFPLUMBER == ParserType.SIMPLE
        assert ParserType.MINERU == ParserType.COMPLEX
        assert ParserType.HYBRID == ParserType.COMPLEX

    def test_parser_type_values(self):
        """测试ParserType值"""
        assert ParserType.SIMPLE.value == "simple"
        assert ParserType.COMPLEX.value == "complex"

    @pytest.fixture
    def selector(self):
        return ParserSelector()

    @pytest.mark.asyncio
    async def test_analyze_document_backward_compat(self, selector):
        """测试_analyze_document向后兼容"""
        with patch.object(selector, 'quick_detect_tables', new_callable=AsyncMock) as mock_detect:
            mock_detect.return_value = (True, 3)

            result = await selector._analyze_document("test.pdf")

            assert "table_count" in result
            assert result["table_count"] == 3

    def test_calculate_complexity_score_backward_compat(self, selector):
        """测试_calculate_complexity_score向后兼容"""
        analysis = {"table_count": 5}
        score = selector._calculate_complexity_score(analysis)
        assert score == 0.8  # 有表格

        analysis = {"table_count": 0}
        score = selector._calculate_complexity_score(analysis)
        assert score == 0.2  # 无表格

    def test_determine_parser_backward_compat(self, selector):
        """测试_determine_parser向后兼容"""
        assert selector._determine_parser(0.1) == ParserType.SIMPLE
        assert selector._determine_parser(0.9) == ParserType.COMPLEX


class TestParserSelectorEdgeCases:
    """边界情况测试"""

    @pytest.fixture
    def selector(self):
        return ParserSelector()

    @pytest.mark.asyncio
    async def test_selection_error_fallback(self, selector):
        """测试选择出错时回退到简单模式"""
        with patch.object(selector, 'quick_detect_tables', new_callable=AsyncMock) as mock_detect:
            mock_detect.side_effect = Exception("Test error")

            result = await selector.select_parser("error.pdf")

            assert result.selected_parser == ParserType.SIMPLE

    def test_to_dict_format(self, selector):
        """测试输出格式"""
        result = selector._create_forced_result("simple")
        result_dict = result.to_dict()

        assert "selected_parser" in result_dict
        assert "parser_mode" in result_dict
        assert "has_tables" in result_dict
        assert "table_count" in result_dict
        assert "reasoning" in result_dict
