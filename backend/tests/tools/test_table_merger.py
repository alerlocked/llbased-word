"""
Table Merger Unit Tests
"""
import pytest
from app.models.table_models import ExtractedTable, TableMetadata, ParserType, TableType
from app.tools.table_merger import TableMerger


class TestTableMerger:
    """Table merger tests"""

    @pytest.fixture
    def merger(self):
        """Create table merger"""
        return TableMerger()

    @pytest.fixture
    def sample_table_page1(self):
        """Create sample table on page 1"""
        metadata = TableMetadata(
            has_merged_cells=False,
            is_continuation=False,
            has_border=True
        )

        return ExtractedTable(
            table_id="table_0_0",
            page_number=0,
            bbox=(100, 100, 500, 800),
            rows=[
                ["工序", "工具", "参数"],
                ["车削", "车刀", "转速1000"],
                ["铣削", "铣刀", "转速800"]
            ],
            columns=3,
            headers=["工序", "工具", "参数"],
            data_rows=[
                ["车削", "车刀", "转速1000"],
                ["铣削", "铣刀", "转速800"]
            ],
            confidence_score=0.95,
            extraction_method="pymupdf",
            parser_used=ParserType.PYMUPDF,
            metadata=metadata,
            table_type=TableType.PROCESS_TABLE
        )

    @pytest.fixture
    def sample_table_page2_continuation(self):
        """Create sample table on page 2 that is a continuation"""
        metadata = TableMetadata(
            has_merged_cells=False,
            is_continuation=True,
            has_border=True
        )

        return ExtractedTable(
            table_id="table_1_0",
            page_number=1,
            bbox=(100, 100, 500, 400),
            rows=[
                ["磨削", "砂轮", "转速1200"],
                ["钻孔", "钻头", "转速500"]
            ],
            columns=3,
            headers=None,
            data_rows=[
                ["磨削", "砂轮", "转速1200"],
                ["钻孔", "钻头", "转速500"]
            ],
            confidence_score=0.92,
            extraction_method="pymupdf",
            parser_used=ParserType.PYMUPDF,
            metadata=metadata,
            table_type=TableType.PROCESS_TABLE
        )

    @pytest.fixture
    def sample_table_page2_new(self):
        """Create sample table on page 2 that is NOT a continuation"""
        metadata = TableMetadata(
            has_merged_cells=False,
            is_continuation=False,
            has_border=True
        )

        return ExtractedTable(
            table_id="table_1_0",
            page_number=1,
            bbox=(100, 100, 500, 400),
            rows=[
                ["产品", "价格", "库存"],
                ["手机", "5000", "100"]
            ],
            columns=3,
            headers=["产品", "价格", "库存"],
            data_rows=[["手机", "5000", "100"]],
            confidence_score=0.90,
            extraction_method="pymupdf",
            parser_used=ParserType.PYMUPDF,
            metadata=metadata,
            table_type=TableType.GENERAL_TABLE
        )

    def test_detect_continuation_true(self, merger, sample_table_page1, sample_table_page2_continuation):
        """Test continuation detection - positive case"""
        result = merger.detect_continuation(sample_table_page1, sample_table_page2_continuation)
        assert result is True

    def test_detect_continuation_false_different_headers(self, merger, sample_table_page1, sample_table_page2_new):
        """Test continuation detection - negative case (different headers)"""
        result = merger.detect_continuation(sample_table_page1, sample_table_page2_new)
        assert result is False

    def test_detect_continuation_false_non_consecutive(self, merger, sample_table_page1):
        """Test continuation detection - negative case (non-consecutive pages)"""
        table_page3 = ExtractedTable(
            table_id="table_2_0",
            page_number=2,  # Not consecutive
            bbox=(100, 100, 500, 400),
            rows=[["工序", "工具", "参数"], ["测试", "工具", "参数"]],
            columns=3,
            headers=["工序", "工具", "参数"],
            confidence_score=0.90,
            extraction_method="pymupdf",
            parser_used=ParserType.PYMUPDF,
            metadata=TableMetadata(),
            table_type=TableType.PROCESS_TABLE
        )

        result = merger.detect_continuation(sample_table_page1, table_page3)
        assert result is False

    def test_merge_two_tables(self, merger, sample_table_page1, sample_table_page2_continuation):
        """Test merging two tables"""
        merged = merger.merge_two_tables(sample_table_page1, sample_table_page2_continuation)

        assert merged.table_id == "table_0_0"
        assert merged.page_number == 0
        assert len(merged.rows) == 5  # 3 rows + 2 rows
        assert merged.columns == 3
        assert merged.headers == ["工序", "工具", "参数"]
        assert merged.extraction_method == "merged"

    def test_detect_and_merge_tables(self, merger, sample_table_page1, sample_table_page2_continuation):
        """Test detecting and merging tables"""
        tables = [sample_table_page1, sample_table_page2_continuation]
        merged_tables = merger.detect_and_merge_tables(tables)

        assert len(merged_tables) == 1
        assert len(merged_tables[0].rows) == 5

    def test_no_merge_when_different_tables(self, merger, sample_table_page1, sample_table_page2_new):
        """Test that different tables are not merged"""
        tables = [sample_table_page1, sample_table_page2_new]
        merged_tables = merger.detect_and_merge_tables(tables)

        assert len(merged_tables) == 2

    def test_check_column_similarity(self, merger):
        """Test column similarity check"""
        table1 = ExtractedTable(
            table_id="t1",
            page_number=0,
            bbox=(0, 0, 100, 100),
            rows=[["工序名称", "操作步骤", "技术要求"]],
            columns=3,
            extraction_method="test",
            parser_used=ParserType.PYMUPDF,
            metadata=TableMetadata(),
            table_type=TableType.GENERAL_TABLE
        )

        table2 = ExtractedTable(
            table_id="t2",
            page_number=1,
            bbox=(0, 0, 100, 100),
            rows=[["工艺名称", "操作方法", "质量要求"]],
            columns=3,
            extraction_method="test",
            parser_used=ParserType.PYMUPDF,
            metadata=TableMetadata(),
            table_type=TableType.GENERAL_TABLE
        )

        # Similar column structure
        result = merger._check_column_similarity(table1, table2)
        assert result is True

    def test_check_header_match_exact(self, merger):
        """Test header match - exact match"""
        table1 = ExtractedTable(
            table_id="t1",
            page_number=0,
            bbox=(0, 0, 100, 100),
            rows=[["A", "B", "C"], ["D", "E", "F"]],
            columns=3,
            headers=["A", "B", "C"],
            extraction_method="test",
            parser_used=ParserType.PYMUPDF,
            metadata=TableMetadata(),
            table_type=TableType.GENERAL_TABLE
        )

        table2 = ExtractedTable(
            table_id="t2",
            page_number=1,
            bbox=(0, 0, 100, 100),
            rows=[["A", "B", "C"], ["G", "H", "I"]],
            columns=3,
            headers=["A", "B", "C"],
            extraction_method="test",
            parser_used=ParserType.PYMUPDF,
            metadata=TableMetadata(),
            table_type=TableType.GENERAL_TABLE
        )

        match_score = merger._check_header_match(table1, table2)
        assert match_score == 1.0

    def test_check_header_match_partial(self, merger):
        """Test header match - partial match"""
        table1 = ExtractedTable(
            table_id="t1",
            page_number=0,
            bbox=(0, 0, 100, 100),
            rows=[["工序", "工具", "参数"]],
            columns=3,
            headers=["工序", "工具", "参数"],
            extraction_method="test",
            parser_used=ParserType.PYMUPDF,
            metadata=TableMetadata(),
            table_type=TableType.GENERAL_TABLE
        )

        table2 = ExtractedTable(
            table_id="t2",
            page_number=1,
            bbox=(0, 0, 100, 100),
            rows=[["工序", "设备", "参数"]],
            columns=3,
            headers=["工序", "设备", "参数"],
            extraction_method="test",
            parser_used=ParserType.PYMUPDF,
            metadata=TableMetadata(),
            table_type=TableType.GENERAL_TABLE
        )

        match_score = merger._check_header_match(table1, table2)
        # 2 exact matches (工序, 参数) out of 3
        assert match_score == pytest.approx(2/3, rel=0.01)

    def test_check_position_consistency(self, merger):
        """Test position consistency check"""
        table1 = ExtractedTable(
            table_id="t1",
            page_number=0,
            bbox=(100, 100, 500, 800),
            rows=[["A"]],
            columns=1,
            extraction_method="test",
            parser_used=ParserType.PYMUPDF,
            metadata=TableMetadata(),
            table_type=TableType.GENERAL_TABLE
        )

        # Same horizontal position
        table2 = ExtractedTable(
            table_id="t2",
            page_number=1,
            bbox=(100, 100, 500, 800),  # Same x coordinates
            rows=[["B"]],
            columns=1,
            extraction_method="test",
            parser_used=ParserType.PYMUPDF,
            metadata=TableMetadata(),
            table_type=TableType.GENERAL_TABLE
        )

        result = merger._check_position_consistency(table1, table2)
        assert result is True

        # Different horizontal position
        table3 = ExtractedTable(
            table_id="t3",
            page_number=1,
            bbox=(200, 100, 600, 800),  # Different x coordinates
            rows=[["C"]],
            columns=1,
            extraction_method="test",
            parser_used=ParserType.PYMUPDF,
            metadata=TableMetadata(),
            table_type=TableType.GENERAL_TABLE
        )

        result = merger._check_position_consistency(table1, table3)
        assert result is False

    def test_is_header_row(self, merger):
        """Test header row detection"""
        row = ["工序", "工具", "参数"]
        headers = ["工序", "工具", "参数"]

        result = merger._is_header_row(row, headers)
        assert result is True

        # Not a header row
        row2 = ["车削", "车刀", "转速1000"]
        result2 = merger._is_header_row(row2, headers)
        assert result2 is False

    def test_merge_empty_table_list(self, merger):
        """Test merging empty table list"""
        result = merger.detect_and_merge_tables([])
        assert result == []

    def test_merge_single_table(self, merger, sample_table_page1):
        """Test merging single table"""
        result = merger.detect_and_merge_tables([sample_table_page1])
        assert len(result) == 1
        assert result[0].table_id == sample_table_page1.table_id
