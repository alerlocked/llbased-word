"""
Search Agent 单元测试

测试覆盖：
- search() 主方法（各种模式）
- 缓存机制（命中/未命中/过期）
- Token 估算
- Token 预算管理
- 分层注入策略
"""
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.search import (
    SearchAgent,
    SearchContext,
    SearchMode,
    SearchResult,
    CacheStats,
    TokenBudget,
)


class TestTokenBudget:
    """Token 预算管理测试"""

    def test_default_allocation(self):
        """测试默认 Token 分配"""
        budget = TokenBudget(4000)
        allocation = budget.get_allocation()

        assert allocation["files"] == 2400  # 60%
        assert allocation["knowledge"] == 1200  # 30%
        assert allocation["buffer"] == 400  # 10%

    def test_custom_max_tokens(self):
        """测试自定义最大 Token 数"""
        budget = TokenBudget(8000)
        allocation = budget.get_allocation()

        assert allocation["files"] == 4800
        assert allocation["knowledge"] == 2400
        assert allocation["buffer"] == 800

    def test_allocation_sum(self):
        """测试分配总和不超过最大值"""
        budget = TokenBudget(4000)
        allocation = budget.get_allocation()

        total = sum(allocation.values())
        assert total <= 4000


class TestSearchAgent:
    """Search Agent 测试"""

    @pytest.fixture
    def agent(self):
        """创建 Search Agent 实例"""
        return SearchAgent({"cache_size": 100, "cache_ttl": 60})

    def test_initialization(self, agent):
        """测试初始化"""
        assert agent._cache_size == 100
        assert agent._cache_ttl == 60
        assert agent.cache_stats.total_requests == 0

    def test_estimate_tokens(self, agent):
        """测试 Token 估算"""
        # 空字符串
        assert agent._estimate_tokens("") == 0

        # 英文文本（约 4 字符/token）
        english = "Hello world this is a test"
        tokens = agent._estimate_tokens(english)
        assert tokens > 0

        # 中文文本（约 1.5 字符/token）
        chinese = "这是一个测试文本"
        tokens = agent._estimate_tokens(chinese)
        assert tokens > 0

    def test_cache_key_generation(self, agent):
        """测试缓存键生成"""
        key1 = agent._make_cache_key(SearchMode.FILES_ONLY, "query1", 1000, None)
        key2 = agent._make_cache_key(SearchMode.FILES_ONLY, "query1", 1000, None)
        key3 = agent._make_cache_key(SearchMode.FILES_ONLY, "query2", 1000, None)

        # 相同参数生成相同键
        assert key1 == key2

        # 不同参数生成不同键
        assert key1 != key3

    def test_cache_hit_and_miss(self, agent):
        """测试缓存命中和未命中"""
        cache_key = "test_key"

        # 第一次访问（未命中）
        result = agent._get_cached(cache_key)
        assert result is None
        assert agent.cache_stats.misses == 1
        assert agent.cache_stats.hits == 0

        # 设置缓存
        context = SearchContext(
            contexts=[],
            total_tokens=0,
            mode=SearchMode.FILES_ONLY
        )
        agent._set_cache(cache_key, context)

        # 第二次访问（命中）
        result = agent._get_cached(cache_key)
        assert result is not None
        assert result.cache_hit == True
        assert agent.cache_stats.hits == 1

    def test_cache_expiration(self, agent):
        """测试缓存过期"""
        agent._cache_ttl = 1  # 1 秒过期

        cache_key = "test_key"
        context = SearchContext(
            contexts=[],
            total_tokens=0,
            mode=SearchMode.FILES_ONLY
        )

        # 设置缓存
        agent._set_cache(cache_key, context)

        # 立即访问（命中）
        result = agent._get_cached(cache_key)
        assert result is not None

        # 等待过期
        time.sleep(1.5)

        # 访问过期缓存（未命中）
        result = agent._get_cached(cache_key)
        assert result is None
        assert agent.cache_stats.evictions >= 1

    def test_cache_eviction(self, agent):
        """测试缓存淘汰（LRU）"""
        agent._cache_size = 3  # 限制为 3 个条目

        for i in range(5):
            context = SearchContext(
                contexts=[],
                total_tokens=0,
                mode=SearchMode.FILES_ONLY
            )
            agent._set_cache(f"key_{i}", context)

        # 缓存大小不应超过限制
        assert len(agent._cache) <= 3
        assert agent.cache_stats.evictions >= 2

    @pytest.mark.asyncio
    async def test_search_files_only(self, agent):
        """测试仅文件检索"""
        with patch.object(agent, '_files_only_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = SearchContext(
                contexts=[
                    SearchResult(
                        content="test content",
                        source="test.pdf",
                        relevance_score=0.9,
                        token_count=10
                    )
                ],
                total_tokens=10,
                mode=SearchMode.FILES_ONLY
            )

            result = await agent.search(
                mode=SearchMode.FILES_ONLY,
                query="test query",
                token_budget=1000
            )

            assert result.mode == SearchMode.FILES_ONLY
            assert len(result.contexts) == 1
            assert result.contexts[0].content == "test content"
            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_knowledge_only(self, agent):
        """测试仅知识图谱检索"""
        with patch.object(agent, '_knowledge_only_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = SearchContext(
                contexts=[
                    SearchResult(
                        content="knowledge content",
                        source="knowledge_graph",
                        relevance_score=0.8,
                        token_count=15,
                        entity_type="Term",
                        entity_id="term_001"
                    )
                ],
                total_tokens=15,
                mode=SearchMode.KNOWLEDGE_ONLY
            )

            result = await agent.search(
                mode=SearchMode.KNOWLEDGE_ONLY,
                query="test query",
                token_budget=1000
            )

            assert result.mode == SearchMode.KNOWLEDGE_ONLY
            assert len(result.contexts) == 1
            assert result.contexts[0].entity_type == "Term"
            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_comprehensive(self, agent):
        """测试综合检索"""
        with patch.object(agent, '_comprehensive_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = SearchContext(
                contexts=[
                    SearchResult(
                        content="file content",
                        source="test.pdf",
                        relevance_score=0.9,
                        token_count=10
                    ),
                    SearchResult(
                        content="knowledge content",
                        source="knowledge_graph",
                        relevance_score=0.8,
                        token_count=15
                    )
                ],
                total_tokens=25,
                mode=SearchMode.COMPREHENSIVE,
                token_allocation={"files": 600, "knowledge": 300, "buffer": 100}
            )

            result = await agent.search(
                mode=SearchMode.COMPREHENSIVE,
                query="test query",
                token_budget=1000
            )

            assert result.mode == SearchMode.COMPREHENSIVE
            assert len(result.contexts) == 2
            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_cache_hit(self, agent):
        """测试搜索缓存命中"""
        with patch.object(agent, '_files_only_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = SearchContext(
                contexts=[],
                total_tokens=0,
                mode=SearchMode.FILES_ONLY
            )

            # 第一次搜索（未命中）
            result1 = await agent.search(
                mode=SearchMode.FILES_ONLY,
                query="test query",
                token_budget=1000
            )
            assert result1.cache_hit == False

            # 第二次搜索（命中）
            result2 = await agent.search(
                mode=SearchMode.FILES_ONLY,
                query="test query",
                token_budget=1000
            )
            assert result2.cache_hit == True

            # 只调用一次实际搜索
            assert mock_search.call_count == 1

    @pytest.mark.asyncio
    async def test_search_error_handling(self, agent):
        """测试搜索错误处理"""
        with patch.object(agent, '_files_only_search', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = Exception("Search failed")

            result = await agent.search(
                mode=SearchMode.FILES_ONLY,
                query="test query",
                token_budget=1000
            )

            # 应该返回空结果而非抛出异常
            assert result.contexts == []
            assert "error" in result.metadata

    def test_clear_cache(self, agent):
        """测试清空缓存"""
        context = SearchContext(
            contexts=[],
            total_tokens=0,
            mode=SearchMode.FILES_ONLY
        )
        agent._set_cache("key1", context)
        agent._set_cache("key2", context)

        assert len(agent._cache) == 2

        agent.clear_cache()

        assert len(agent._cache) == 0
        assert agent.cache_stats.total_requests == 0

    def test_get_cache_info(self, agent):
        """测试获取缓存信息"""
        info = agent.get_cache_info()

        assert "size" in info
        assert "max_size" in info
        assert "ttl" in info
        assert "stats" in info
        assert "hit_rate" in info["stats"]


class TestSearchResult:
    """SearchResult 测试"""

    def test_creation(self):
        """测试创建搜索结果"""
        result = SearchResult(
            content="test content",
            source="test.pdf",
            relevance_score=0.9,
            token_count=100,
            metadata={"page": 1}
        )

        assert result.content == "test content"
        assert result.source == "test.pdf"
        assert result.relevance_score == 0.9
        assert result.token_count == 100
        assert result.metadata["page"] == 1

    def test_knowledge_graph_fields(self):
        """测试知识图谱字段"""
        result = SearchResult(
            content="term definition",
            source="knowledge_graph",
            relevance_score=0.8,
            token_count=50,
            entity_type="Term",
            entity_id="term_001",
            relations=[{"type": "is_a", "target": "parent_term"}]
        )

        assert result.entity_type == "Term"
        assert result.entity_id == "term_001"
        assert len(result.relations) == 1


class TestSearchContext:
    """SearchContext 测试"""

    def test_creation(self):
        """测试创建搜索上下文"""
        context = SearchContext(
            contexts=[
                SearchResult(
                    content="content 1",
                    source="source 1",
                    relevance_score=0.9,
                    token_count=100
                )
            ],
            total_tokens=100,
            mode=SearchMode.FILES_ONLY,
            cache_hit=True
        )

        assert len(context.contexts) == 1
        assert context.total_tokens == 100
        assert context.cache_hit == True

    def test_token_allocation(self):
        """测试 Token 分配"""
        context = SearchContext(
            contexts=[],
            total_tokens=0,
            mode=SearchMode.COMPREHENSIVE,
            token_allocation={"files": 600, "knowledge": 300, "buffer": 100}
        )

        assert context.token_allocation["files"] == 600
        assert context.token_allocation["knowledge"] == 300


class TestCacheStats:
    """CacheStats 测试"""

    def test_hit_rate_calculation(self):
        """测试命中率计算"""
        stats = CacheStats(hits=8, misses=2, total_requests=10)

        assert stats.hit_rate == 0.8

    def test_zero_requests_hit_rate(self):
        """测试零请求时的命中率"""
        stats = CacheStats()

        assert stats.hit_rate == 0.0
