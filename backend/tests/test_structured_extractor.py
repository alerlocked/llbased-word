"""
Tests for structured field extraction and fill_type grouping.

Covers:
- fill_type grouping from template columns
- Structured field extraction from mock source text
- Merge of structured + unstructured into final rows
"""
import pytest
from app.services.template_types import TemplateColumn
from app.services.structured_extractor import (
    extract_structured_fields,
    merge_structured_with_unstructured,
    _parse_source_rows,
)
from app.services.template_loader import get_columns_by_fill_type
from app.services.template_types import TemplateChapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_col(key: str, label: str, fill_type: str = "structured",
              ai_filled: bool = False) -> TemplateColumn:
    return TemplateColumn(
        key=key, label=label, fill_type=fill_type, ai_filled=ai_filled
    )


# ---------------------------------------------------------------------------
# Tests: fill_type grouping
# ---------------------------------------------------------------------------

class TestFillTypeGrouping:
    def test_group_mixed_columns(self):
        """Columns with mixed fill_types are correctly separated."""
        cols = [
            _make_col("workshop", "车间", "structured"),
            _make_col("step_no", "工序号", "structured"),
            _make_col("content", "工序内容", "unstructured", ai_filled=True),
            _make_col("inspection", "检验", "unstructured", ai_filled=True),
            _make_col("aux_materials", "辅助材料", "structured"),
        ]
        chapter = TemplateChapter(
            code="G25a", title="装配工艺卡片", table_type="process_card",
            columns=cols,
        )
        grouped = get_columns_by_fill_type(chapter)

        assert len(grouped["structured"]) == 3
        assert len(grouped["unstructured"]) == 2
        assert grouped["structured"][0].key == "workshop"
        assert grouped["unstructured"][0].key == "content"

    def test_all_structured(self):
        """All-structured chapter returns empty unstructured list."""
        cols = [
            _make_col("seq", "序号", "structured"),
            _make_col("doc_name", "文件名称", "structured"),
        ]
        chapter = TemplateChapter(
            code="G4a", title="工艺文件目录", table_type="single_row_list",
            columns=cols,
        )
        grouped = get_columns_by_fill_type(chapter)

        assert len(grouped["structured"]) == 2
        assert len(grouped["unstructured"]) == 0


# ---------------------------------------------------------------------------
# Tests: structured field extraction
# ---------------------------------------------------------------------------

class TestStructuredExtraction:
    def test_extract_from_markdown_table(self):
        """Extract structured fields from a Markdown table in source text."""
        source = """| 序号 | 车间 | 工序号 | 工序名称 | 辅助材料 |
|------|------|--------|----------|----------|
| 1 | 一车间 | 1 | 装前准备 | 酒精 |
| 2 | 一车间 | 2 | 安装密封圈 | 密封胶 |
| 3 | 二车间 | 3 | 对接 | 无 |
"""
        cols = [
            _make_col("step_no", "工序号", "structured"),
            _make_col("workshop", "车间", "structured"),
            _make_col("aux_materials", "辅助材料", "structured"),
        ]

        result = extract_structured_fields("G25a", cols, source)

        assert len(result["workshop"]) == 3
        assert result["workshop"][0] == "一车间"
        assert len(result["step_no"]) == 3
        assert len(result["aux_materials"]) == 3
        assert result["aux_materials"][0] == "酒精"

    def test_extract_empty_source(self):
        """Empty source returns empty value lists."""
        cols = [_make_col("workshop", "车间", "structured")]
        result = extract_structured_fields("G25a", cols, "")

        assert result == {"workshop": []}

    def test_extract_singleton_field(self):
        """Extract a singleton field from non-table text."""
        source = "车间 一车间\n工序内容 这是详细描述..."
        cols = [_make_col("workshop", "车间", "structured")]

        result = extract_structured_fields("G22a", cols, source)

        assert len(result["workshop"]) == 1
        assert result["workshop"][0] == "一车间"


# ---------------------------------------------------------------------------
# Tests: merge
# ---------------------------------------------------------------------------

class TestMerge:
    def test_merge_structured_and_unstructured(self):
        """Merge structured values with LLM-generated slots."""
        structured = {
            "workshop": ["一车间", "一车间"],
            "step_no": ["1", "2"],
        }
        unstructured = [
            {"row": 1, "slot": "content", "value": "工序1内容..."},
            {"row": 1, "slot": "inspection", "value": "检查要点..."},
            {"row": 2, "slot": "content", "value": "工序2内容..."},
            {"row": 2, "slot": "inspection", "value": "检查要点2..."},
        ]

        rows = merge_structured_with_unstructured(structured, unstructured, 2)

        assert len(rows) == 2
        assert rows[0]["workshop"] == "一车间"
        assert rows[0]["step_no"] == "1"
        assert rows[0]["content"] == "工序1内容..."
        assert rows[0]["inspection"] == "检查要点..."
        assert rows[1]["workshop"] == "一车间"
        assert rows[1]["content"] == "工序2内容..."

    def test_merge_only_structured(self):
        """Merge with empty unstructured slots returns structured-only rows."""
        structured = {"workshop": ["一车间"], "step_no": ["1"]}
        rows = merge_structured_with_unstructured(structured, [], 1)

        assert len(rows) == 1
        assert rows[0]["workshop"] == "一车间"
        assert rows[0]["step_no"] == "1"

    def test_merge_only_unstructured(self):
        """Merge with empty structured values uses defaults."""
        unstructured = [
            {"row": 1, "slot": "content", "value": "测试内容"},
        ]
        rows = merge_structured_with_unstructured({}, unstructured, 1)

        assert len(rows) == 1
        assert rows[0]["content"] == "测试内容"


# ---------------------------------------------------------------------------
# Tests: _parse_source_rows
# ---------------------------------------------------------------------------

class TestParseSourceRows:
    def test_parse_markdown_table(self):
        text = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
        rows = _parse_source_rows(text)
        # Header row is included, separator row is filtered
        assert len(rows) == 3
        assert rows[0] == ["A", "B"]
        assert rows[1] == ["1", "2"]
        assert rows[2] == ["3", "4"]

    def test_parse_no_table(self):
        text = "Just some text\nwithout any table"
        rows = _parse_source_rows(text)
        assert rows == []

    def test_parse_tab_separated(self):
        text = "a\tb\tc\n1\t2\t3"
        rows = _parse_source_rows(text)
        assert len(rows) == 2
        assert rows[1] == ["1", "2", "3"]


# ---------------------------------------------------------------------------
# Tests: 双层列头材料表 (G12a/G14a) — 真实 fixture (documents/1/content.html)
# commit1 (A+B+B+): material_desc 抽真材料名, 不被短别名 名称 抢列.
# quota 噪声 (净重/单套) 断言在 commit2/3 (C 双层合并) 后加.
# ---------------------------------------------------------------------------

class TestDualHeaderMaterialTables:
    def test_g12a_material_desc_real(self):
        from tests.fixtures.material_tables import G12A_MD
        cols = [
            _make_col("seq", "序号"),
            _make_col("part_code", "代号"),
            _make_col("part_name", "名称"),
            _make_col("material_desc", "材料名称"),
            _make_col("unit", "计量单位"),
            _make_col("quota", "定额"),
        ]
        res = extract_structured_fields("G12a", cols, G12A_MD)
        # B+: material_desc grabs the material cell (长 label 先占), not part_name
        assert res["material_desc"][0] == "硫化硅橡胶GD414"
        assert len(res["material_desc"]) == 6
        assert "硫化硅橡胶GD414" not in res.get("part_name", [])
        assert len(res["seq"]) == 6
        # C: subheader row skipped → 净重 label not read as data; quota is the 定额 values
        assert "净重" not in res["quota"]
        assert res["quota"] == ["0.1", "15", "0.2", "4", "20", "2"]

    def test_g14a_material_desc_space_label(self):
        from tests.fixtures.material_tables import G14A_MD
        cols = [
            _make_col("seq", "序号"),
            _make_col("material_desc", "材料名称"),
            _make_col("unit", "计量单位"),
            _make_col("per_set_quota", "定额"),
        ]
        res = extract_structured_fields("G14a", cols, G14A_MD)
        # A+B: source header "材 料" (含空格) matches via alias "材料" + whitespace strip
        assert res["material_desc"] == ["白棉布(1.2m宽)"]
