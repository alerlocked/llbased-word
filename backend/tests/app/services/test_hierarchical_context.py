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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
