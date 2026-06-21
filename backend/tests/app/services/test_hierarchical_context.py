"""
测试 hierarchical_context.py 中的上下文检索功能
"""
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# 添加 backend 目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))


class TestExtractKeywords:
    """测试关键词提取功能"""

    def test_extract_chinese_keywords(self):
        """测试中文关键词提取"""
        from app.services.hierarchical_context import extract_keywords
        keywords = extract_keywords("装配工艺卡片有多少页")
        # 应该包含有意义的中文词组
        assert len(keywords) > 0
        # 不应该包含单字或停用词
        for kw in keywords:
            assert len(kw) > 1

    def test_extract_english_keywords(self):
        """测试英文关键词提取"""
        from app.services.hierarchical_context import extract_keywords
        keywords = extract_keywords("What is G4a table?")
        assert 'table' in keywords

    def test_extract_mixed_keywords(self):
        """测试中英混合关键词提取"""
        from app.services.hierarchical_context import extract_keywords
        keywords = extract_keywords("G4a 表格包含什么内容")
        assert 'g4a' in keywords or 'G4a' in str(keywords)

    def test_filter_stopwords(self):
        """测试停用词过滤"""
        from app.services.hierarchical_context import extract_keywords
        keywords = extract_keywords("这是我的文档")
        # 停用词"是"和"的"应该被过滤，"文档"应该保留
        # 注意：jieba分词可能会产生不同的结果，所以只检查基本功能
        # 单个字符会被过滤掉，所以结果中不应该有单字
        for kw in keywords:
            assert len(kw) > 1
        # "文档"应该被正确提取
        assert '文档' in keywords


class TestHierarchicalContext:
    """测试分层上下文管理器"""

    @pytest.fixture
    def mock_data_dir(self, tmp_path):
        """创建模拟数据目录"""
        # 创建文档目录
        doc_dir = tmp_path / "test_doc"
        doc_dir.mkdir()

        # 创建 index.json
        index_data = {
            "name": "测试工艺文档",
            "pages": 10,
            "tables": [
                {
                    "id": "G4a",
                    "type": "装配工艺卡片",
                    "page": 5,
                    "summary": "包含车削工艺参数，如切削速度、进给量等"
                }
            ],
            "materials": ["45号钢", "铝合金"]
        }

        import json
        with open(doc_dir / "index.json", "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False)

        # 创建空的 document.html
        with open(doc_dir / "document.html", "w", encoding="utf-8") as f:
            f.write("<html><body><table id='G4a'><tr><td>Test</td></tr></table></body></html>")

        return tmp_path

    def test_load_meta_index(self, mock_data_dir):
        """测试加载元信息索引"""
        from app.services.hierarchical_context import HierarchicalContext
        ctx = HierarchicalContext(data_dir=str(mock_data_dir))
        meta = ctx.load_meta_index()

        assert "测试工艺文档" in meta
        assert "10" in meta
        assert "G4a" in meta

    def test_load_table_index(self, mock_data_dir):
        """测试加载表格索引"""
        from app.services.hierarchical_context import HierarchicalContext
        ctx = HierarchicalContext(data_dir=str(mock_data_dir))
        table_index = ctx.load_table_index()

        assert "G4a" in table_index
        assert "装配工艺卡片" in table_index

    def test_search_tables_by_id(self, mock_data_dir):
        """测试通过表格ID搜索"""
        from app.services.hierarchical_context import HierarchicalContext
        ctx = HierarchicalContext(data_dir=str(mock_data_dir))
        matches = ctx.search_tables("G4a")

        assert len(matches) > 0
        assert matches[0].table_id == "G4a"

    def test_search_tables_by_type(self, mock_data_dir):
        """测试通过表格类型搜索"""
        from app.services.hierarchical_context import HierarchicalContext
        ctx = HierarchicalContext(data_dir=str(mock_data_dir))
        matches = ctx.search_tables("装配工艺卡片")

        assert len(matches) > 0
        assert "工艺卡片" in matches[0].table_type

    def test_search_meta_info_page_query(self, mock_data_dir):
        """测试元信息查询：页数查询"""
        from app.services.hierarchical_context import HierarchicalContext
        ctx = HierarchicalContext(data_dir=str(mock_data_dir))

        result = ctx.search_meta_info("测试工艺文档有多少页")
        assert result is not None
        assert "10" in result
        assert "页" in result

    def test_search_meta_info_location_query(self, mock_data_dir):
        """测试元信息查询：位置查询"""
        from app.services.hierarchical_context import HierarchicalContext
        ctx = HierarchicalContext(data_dir=str(mock_data_dir))

        result = ctx.search_meta_info("G4a表格在哪个文档")
        assert result is not None
        assert "G4a" in result

    def test_search_meta_info_material_query(self, mock_data_dir):
        """测试元信息查询：材料查询"""
        from app.services.hierarchical_context import HierarchicalContext
        ctx = HierarchicalContext(data_dir=str(mock_data_dir))

        result = ctx.search_meta_info("有哪些材料")
        assert result is not None
        assert "45号钢" in result or "铝合金" in result

    def test_build_context(self, mock_data_dir):
        """测试构建上下文"""
        from app.services.hierarchical_context import HierarchicalContext
        ctx = HierarchicalContext(data_dir=str(mock_data_dir))

        context = ctx.build_context("G4a表格", "test_session")
        assert len(context) > 0
        assert "G4a" in context

    def test_clear_session(self, mock_data_dir):
        """测试清除会话缓存"""
        from app.services.hierarchical_context import HierarchicalContext
        ctx = HierarchicalContext(data_dir=str(mock_data_dir))

        # 先加载
        ctx.build_context("test", "test_session")
        assert "test_session_layer0" in ctx._loaded_sessions

        # 清除
        ctx.clear_session("test_session")
        assert "test_session_layer0" not in ctx._loaded_sessions


class TestTableMatch:
    """测试表格匹配结果类"""

    def test_table_match_creation(self):
        """测试创建表格匹配结果"""
        from app.services.hierarchical_context import TableMatch
        match = TableMatch(
            doc_name="测试文档",
            table_id="G4a",
            table_type="工艺卡片",
            page=5,
            summary="测试摘要",
            score=10.0
        )

        assert match.doc_name == "测试文档"
        assert match.table_id == "G4a"
        assert match.table_type == "工艺卡片"
        assert match.page == 5
        assert match.summary == "测试摘要"
        assert match.score == 10.0


def _ctx():
    """Build a HierarchicalContext instance for unit tests (no data dir needed
    for _table_to_markdown / _has_colspan_rowspan / _expand_table_grid)."""
    from app.services.hierarchical_context import HierarchicalContext
    return HierarchicalContext(data_dir="/tmp/nonexistent_hctx_test")


class TestTableToMarkdown:
    """测试 _table_to_markdown 的 colspan/rowspan 网格展开"""

    def _parse(self, html: str):
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, "html.parser").find("table")

    def test_has_colspan_rowspan_false_for_plain_table(self):
        """无 colspan/rowspan 的表，护栏返回 False"""
        t = self._parse("<table><tr><td>a</td><td>b</td></tr></table>")
        assert _ctx()._has_colspan_rowspan(t) is False

    def test_has_colspan_rowspan_true_for_colspan(self):
        """有 colspan>1 的表，护栏返回 True"""
        t = self._parse('<table><tr><td colspan="2">a</td></tr></table>')
        assert _ctx()._has_colspan_rowspan(t) is True

    def test_has_colspan_rowspan_true_for_rowspan(self):
        """有 rowspan>1 的表，护栏返回 True"""
        t = self._parse('<table><tr><td rowspan="2">a</td></tr></table>')
        assert _ctx()._has_colspan_rowspan(t) is True

    def test_colspan_expands_text_in_first_col(self):
        """colspan=2 的 td：文本落在首列，次列为空，保持网格对齐"""
        t = self._parse(
            '<table>'
            "<tr><td>H1</td><td>H2</td><td>H3</td></tr>"
            '<tr><td colspan="2">SPAN</td><td>x</td></tr>'
            "</table>"
        )
        md = _ctx()._table_to_markdown(t)
        lines = md.split("\n")
        # line 0 = header, line 1 = separator, line 2 = colspan row
        row_cells = [c.strip() for c in lines[2].split("|")]
        # split("|") yields ['', 'H1', 'H2', 'H3', ''] -> cells
        # SPAN should be in first data column, second column empty
        nonempty = [c for c in row_cells if c]
        assert "SPAN" in nonempty
        # the colspan row must align to 3 columns total like the header
        assert len([c for c in row_cells]) == 5  # leading+trailing empty from split
        # SPAN occupies col0, col1 empty, x in col2
        assert row_cells[1] == "SPAN"
        assert row_cells[2] == ""
        assert row_cells[3] == "x"

    def test_rowspan_leaves_cell_empty_in_following_row(self):
        """rowspan=2 的 td：下一行对应列为空"""
        t = self._parse(
            '<table>'
            "<tr><td>H1</td><td>H2</td></tr>"
            '<tr><td rowspan="2">RS</td><td>a</td></tr>'
            "<tr><td>b</td></tr>"
            "</table>"
        )
        md = _ctx()._table_to_markdown(t)
        lines = md.split("\n")
        # data rows: line2 (RS,a), line3 (b in col1, col0 empty)
        row3_cells = [c.strip() for c in lines[3].split("|")]
        # col0 occupied by rowspan -> empty; b lands in col1
        assert row3_cells[1] == ""  # rowspan owner column
        assert row3_cells[2] == "b"

    def test_mixed_colspan_rowspan_uniform_columns(self):
        """混合 colspan+rowspan：所有行列数一致"""
        t = self._parse(
            '<table>'
            "<tr><td>H1</td><td>H2</td><td>H3</td><td>H4</td></tr>"
            '<tr><td rowspan="2" colspan="2">BIG</td><td>c</td><td>d</td></tr>'
            "<tr><td>e</td><td>f</td></tr>"
            "</table>"
        )
        ctx = _ctx()
        md = ctx._table_to_markdown(t)
        lines = md.split("\n")
        # every row line must have the same number of pipe-delimited cells
        counts = {len([c for c in ln.split("|")]) for ln in lines}
        assert len(counts) == 1, f"column counts differ: {counts}"

    def test_plain_table_uses_legacy_path(self):
        """无 colspan 表走原逻辑（护栏），输出正常 markdown 表"""
        t = self._parse(
            '<table>'
            "<tr><td>车间</td><td>工序号</td></tr>"
            "<tr><td>33</td><td>1</td></tr>"
            "</table>"
        )
        md = _ctx()._table_to_markdown(t)
        assert "车间" in md
        assert "33" in md
        # header separator present
        assert "---" in md

    def test_signature_row_per_cell_not_cross_cell(self):
        """签名行检测基于单元格内数字，不误伤跨格拼接的伪数字串。
        模拟 G25a op5 bug：材料编号尾 3596 与相邻 75mm 拼成 359675 会误删行。
        """
        t = self._parse(
            '<table>'
            "<tr><td>工序内容</td><td>材料</td><td>规格</td></tr>"
            "<tr><td>5.1.1安装电缆</td><td>胶带HG/T3596</td><td>75mm</td></tr>"
            "</table>"
        )
        md = _ctx()._table_to_markdown(t)
        # The real step row must survive (not deleted as a fake signature row)
        assert "5.1.1安装电缆" in md
        assert "HG/T3596" in md


class TestExtractAssemblySteps:
    """测试 extract_assembly_steps 对 colspan 工序卡的解析"""

    def test_extract_substeps_from_colspan_card(self, monkeypatch):
        """含 colspan 的工序卡（类似 op5 结构）应抽到 >=3 substeps。
        改前逐 tr 收集 + pad 会列错位，只抽到 1 个。
        """
        from app.services.hierarchical_context import HierarchicalContext

        # Build a G25a-style HTML: header row (车间/工序号/工序内容) + step
        # header + 3 substeps each in a colspan=7 td, mimicking the real op5
        # table layout where 工序内容 spans multiple columns.
        card_html = (
            "## 第1页\n"
            "<table>"
            "<tr><td>车间</td><td>工序号</td><td>工序名称</td>"
            '<td colspan="7">工序内容</td><td>辅助材料</td></tr>'
            "<tr><td>33</td><td>5</td><td>钳</td><td>五舱装配</td><td></td></tr>"
            "<tr><td></td><td></td><td></td>"
            '<td colspan="7">5.1四舱电缆插接</td><td>黑色胶带</td></tr>'
            "<tr><td></td><td></td><td></td>"
            '<td colspan="7">5.1.1将电缆W14的XG14与电缆W15连接</td><td>胶带</td></tr>'
            "<tr><td></td><td></td><td></td>"
            '<td colspan="7">5.1.2将电缆W17的XG24与四舱连接</td><td>无碱玻璃胶带</td></tr>'
            "<tr><td></td><td></td><td></td>"
            '<td colspan="7">5.1.3将W64D的X63用黑绝缘胶带保护</td><td></td></tr>'
            "</table>"
        )

        ctx = _ctx()
        # Stub get_pages_content to return our crafted markdown-converted text.
        # Route through _html_to_readable so _table_to_markdown runs.
        from bs4 import BeautifulSoup

        def fake_get_pages_content(self, doc_dir_name, start, end, max_tokens=12000):
            soup = BeautifulSoup(card_html, "html.parser")
            return self._html_to_readable(soup)

        monkeypatch.setattr(
            HierarchicalContext, "get_pages_content", fake_get_pages_content
        )
        # Stub load_chapter_index to return one 装配 chapter.
        monkeypatch.setattr(
            HierarchicalContext,
            "load_chapter_index",
            lambda self, name: {"chapters": [{"title": "装配工艺卡片", "pages": [1]}]},
        )

        steps = ctx.extract_assembly_steps("dummy")
        assert 5 in steps, f"step 5 missing, got {list(steps.keys())}"
        subs = steps[5]["substeps"]
        # Before the fix only 1 substep survived; now all 3 real substeps
        # (5.1, 5.1.1, 5.1.2, 5.1.3) should be captured.
        assert len(subs) >= 3, f"expected >=3 substeps, got {len(subs)}: {[s['content'] for s in subs]}"
        contents = " ".join(s["content"] for s in subs)
        assert "5.1.1" in contents
        assert "5.1.2" in contents
        assert "5.1.3" in contents


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
