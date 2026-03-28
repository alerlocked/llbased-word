"""
分层上下文管理器测试

测试 hierarchical_context.py 的核心功能
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestHierarchicalContextBasics:
    """基础功能测试"""

    @pytest.fixture
    def ctx(self):
        """创建 HierarchicalContext 实例"""
        from app.services.hierarchical_context import HierarchicalContext
        # 使用实际的 exports_html 目录
        data_dir = project_root.parent / "data" / "exports_html"
        return HierarchicalContext(data_dir=str(data_dir))

    def test_load_meta_index(self, ctx):
        """测试 Layer 0 加载"""
        meta = ctx.load_meta_index()

        # 验证基本结构
        assert "参考文档索引" in meta or "参考文档" in meta

        # 验证缓存
        assert ctx._meta_cache is not None

        # 再次加载应该使用缓存
        meta2 = ctx.load_meta_index()
        assert meta2 == meta

    def test_load_table_index(self, ctx):
        """测试 Layer 1 加载"""
        index = ctx.load_table_index()

        # 验证基本结构
        assert "表格索引" in index

        # 验证缓存
        assert ctx._table_index_cache is not None

    def test_search_tables_by_id(self, ctx):
        """测试表格 ID 搜索"""
        # 使用实际存在的表格 ID
        results = ctx.search_tables("G4a")

        # 应该找到匹配的表格
        assert len(results) > 0

        # 验证结果结构
        match = results[0]
        assert hasattr(match, 'table_id')
        assert hasattr(match, 'doc_name')
        assert hasattr(match, 'score')
        assert match.score > 0

    def test_search_tables_by_type(self, ctx):
        """测试表格类型搜索"""
        results = ctx.search_tables("工序卡片")

        # 应该找到匹配的表格
        assert len(results) > 0

    def test_search_tables_by_material(self, ctx):
        """测试材料名称搜索"""
        results = ctx.search_tables("GD414")

        # 如果有包含该材料的表格，应该能找到
        # 结果取决于实际数据
        assert isinstance(results, list)

    def test_search_meta_info_pages(self, ctx):
        """测试元信息查询 - 页数"""
        # 测试页数查询
        result = ctx.search_meta_info("全单电缆装配规程有多少页")

        # 应该返回页数信息
        assert result is not None
        assert "页" in result or "44" in result

    def test_search_meta_info_materials(self, ctx):
        """测试元信息查询 - 材料列表"""
        result = ctx.search_meta_info("有哪些材料")

        # 应该返回材料信息
        assert result is not None
        # 可能包含已知材料
        assert "材料" in result

    def test_extract_table_html(self, ctx):
        """测试表格 HTML 提取"""
        # 使用实际存在的表格
        doc_dir = None
        table_id = None

        # 获取第一个可用的文档和表格
        documents = ctx._get_all_documents()
        if documents:
            doc = documents[0]
            doc_dir = doc.get("_doc_dir")
            if doc.get("tables"):
                table_id = doc["tables"][0].get("id")

        if doc_dir and table_id:
            html = ctx.extract_table_html(doc_dir, table_id)

            # 应该返回字符串
            assert isinstance(html, str)
            assert len(html) > 0

    def test_build_context(self, ctx):
        """测试完整上下文构建"""
        context = ctx.build_context(
            query="G4a 是什么？",
            session_id="test-session-001",
            max_tokens=15000
        )

        # 验证上下文不为空
        assert len(context) > 0

        # 验证包含关键内容
        assert "G4a" in context or "参考文档" in context

    def test_build_context_session_caching(self, ctx):
        """测试会话级缓存"""
        session_id = "test-session-cache-001"

        # 第一次构建
        context1 = ctx.build_context(
            query="测试查询",
            session_id=session_id,
            max_tokens=15000
        )

        # 第二次构建应该复用 Layer 0/1
        context2 = ctx.build_context(
            query="另一个查询",
            session_id=session_id,
            max_tokens=15000
        )

        # 验证会话已加载
        assert f"{session_id}_layer0" in ctx._loaded_sessions
        assert f"{session_id}_layer1" in ctx._loaded_sessions

    def test_clear_session(self, ctx):
        """测试清除会话缓存"""
        session_id = "test-session-clear-001"

        # 先构建上下文
        ctx.build_context(
            query="测试",
            session_id=session_id,
            max_tokens=15000
        )

        # 清除缓存
        ctx.clear_session(session_id)

        # 验证会话缓存已清除
        assert f"{session_id}_layer0" not in ctx._loaded_sessions
        assert f"{session_id}_layer1" not in ctx._loaded_sessions

    def test_estimate_tokens(self, ctx):
        """测试 token 估算"""
        # 简单估算测试
        text = "这是一个测试文本"
        tokens = ctx._estimate_tokens(text)

        # 应该返回正整数
        assert tokens > 0
        assert isinstance(tokens, int)


class TestHierarchicalContextEdgeCases:
    """边界情况测试"""

    def test_empty_query(self):
        """测试空查询"""
        from app.services.hierarchical_context import HierarchicalContext
        data_dir = project_root.parent / "data" / "exports_html"
        ctx = HierarchicalContext(data_dir=str(data_dir))

        # 空查询不应该崩溃
        results = ctx.search_tables("")
        assert isinstance(results, list)

    def test_nonexistent_table_id(self):
        """测试不存在的表格 ID"""
        from app.services.hierarchical_context import HierarchicalContext
        data_dir = project_root.parent / "data" / "exports_html"
        ctx = HierarchicalContext(data_dir=str(data_dir))

        results = ctx.search_tables("NONEXISTENT_TABLE_12345")
        # 不存在的 ID 应该返回空列表
        assert len(results) == 0

    def test_nonexistent_directory(self, tmp_path):
        """测试不存在的数据目录"""
        from app.services.hierarchical_context import HierarchicalContext

        # 使用临时空目录
        ctx = HierarchicalContext(data_dir=str(tmp_path / "nonexistent"))

        # 不应该崩溃
        meta = ctx.load_meta_index()
        assert "没有可用的工艺文档" in meta or "参考文档" in meta


class TestKeywordExtraction:
    """关键词提取测试"""

    def test_extract_keywords_chinese(self):
        """测试中文关键词提取"""
        from app.services.hierarchical_context import extract_keywords

        keywords = extract_keywords("工艺文件目录包含产品基本信息")

        # 应该提取出有意义的词
        assert isinstance(keywords, set)
        # 至少应该有一些关键词
        assert len(keywords) > 0

    def test_extract_keywords_mixed(self):
        """测试中英文混合关键词提取"""
        from app.services.hierarchical_context import extract_keywords

        keywords = extract_keywords("G4a 工艺卡片包含 GD414 材料")

        # 应该提取出中英文关键词
        assert isinstance(keywords, set)
        # 应该包含 G4a 或 gd414
        lower_keywords = {k.lower() for k in keywords}
        assert 'g4a' in lower_keywords or 'gd414' in lower_keywords


class TestTableMatch:
    """TableMatch 类测试"""

    def test_table_match_creation(self):
        """测试 TableMatch 创建"""
        from app.services.hierarchical_context import TableMatch

        match = TableMatch(
            doc_name="测试文档",
            table_id="G4a",
            table_type="工艺文件目录",
            page=2,
            summary="测试摘要",
            score=5.0
        )

        assert match.doc_name == "测试文档"
        assert match.table_id == "G4a"
        assert match.table_type == "工艺文件目录"
        assert match.page == 2
        assert match.summary == "测试摘要"
        assert match.score == 5.0
        assert match.tokens == 0  # 默认值


# 运行测试的入口
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
