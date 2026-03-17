"""
Search Agent - 统一检索服务

提供统一的检索接口，支持多种检索模式：
- files_only: 仅检索素材库文件
- knowledge_only: 仅检索知识图谱
- comprehensive: 综合检索（分层注入）

功能特性：
- LRU缓存机制
- Token预算管理
- 分层注入策略
"""
import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple
import os

from app.shared.logging import get_logger

logger = get_logger(__name__)


class SearchMode(str, Enum):
    """检索模式"""
    FILES_ONLY = "files_only"
    KNOWLEDGE_ONLY = "knowledge_only"
    STANDARDS_ONLY = "standards_only"
    COMPREHENSIVE = "comprehensive"


@dataclass
class SearchResult:
    """单个检索结果"""
    content: str
    source: str
    relevance_score: float = 0.0
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 知识图谱相关字段
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    relations: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class SearchContext:
    """检索上下文结果"""
    contexts: List[SearchResult]
    total_tokens: int
    mode: SearchMode
    cache_hit: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Token分配详情
    token_allocation: Dict[str, int] = field(default_factory=dict)

    # 检索统计
    search_stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheStats:
    """缓存统计"""
    hits: int = 0
    misses: int = 0
    total_requests: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests


class TokenBudget:
    """Token预算管理"""

    # 默认配置
    MAX_TOKENS = int(os.getenv("SEARCH_MAX_TOKENS", "4000"))
    FILES_RATIO = float(os.getenv("SEARCH_FILES_RATIO", "0.6"))
    KNOWLEDGE_RATIO = float(os.getenv("SEARCH_KNOWLEDGE_RATIO", "0.3"))
    BUFFER_RATIO = float(os.getenv("SEARCH_BUFFER_RATIO", "0.1"))

    def __init__(self, max_tokens: Optional[int] = None):
        """
        初始化Token预算

        Args:
            max_tokens: 最大Token数量，默认从环境变量读取
        """
        self.max_tokens = max_tokens or self.MAX_TOKENS
        self._validate_ratios()

    def _validate_ratios(self):
        """验证比例配置"""
        total = self.FILES_RATIO + self.KNOWLEDGE_RATIO + self.BUFFER_RATIO
        if abs(total - 1.0) > 0.01:
            logger.warning(
                "token_budget_ratios_invalid",
                files_ratio=self.FILES_RATIO,
                knowledge_ratio=self.KNOWLEDGE_RATIO,
                buffer_ratio=self.BUFFER_RATIO,
                total=total
            )

    def get_allocation(self) -> Dict[str, int]:
        """
        获取Token分配

        Returns:
            各部分的Token分配数量
        """
        return {
            "files": int(self.max_tokens * self.FILES_RATIO),
            "knowledge": int(self.max_tokens * self.KNOWLEDGE_RATIO),
            "buffer": int(self.max_tokens * self.BUFFER_RATIO),
        }


class SearchAgent:
    """
    统一检索Agent

    提供统一的检索接口，整合素材库文件检索和知识图谱检索。

    使用方式:
        agent = SearchAgent()
        result = await agent.search(
            mode=SearchMode.COMPREHENSIVE,
            query="电缆装配工艺",
            token_budget=4000
        )
    """

    # 缓存配置
    CACHE_SIZE = int(os.getenv("SEARCH_AGENT_CACHE_SIZE", "1000"))
    CACHE_TTL = int(os.getenv("SEARCH_AGENT_CACHE_TTL", "300"))  # 秒

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化Search Agent

        Args:
            config: 配置参数
                - cache_size: 缓存大小
                - cache_ttl: 缓存TTL（秒）
                - max_tokens: 默认Token预算
        """
        self.config = config or {}

        # 缓存配置
        self._cache_size = self.config.get("cache_size", self.CACHE_SIZE)
        self._cache_ttl = self.config.get("cache_ttl", self.CACHE_TTL)

        # 内存缓存（用于统计）
        self._cache: Dict[str, Tuple[SearchContext, float]] = {}
        self._cache_stats = CacheStats()

        # Token预算
        self._default_budget = TokenBudget(
            max_tokens=self.config.get("max_tokens")
        )

        # 依赖服务（延迟初始化）
        self._file_selector = None
        self._ontology_service = None

        logger.info(
            "search_agent_initialized",
            cache_size=self._cache_size,
            cache_ttl=self._cache_ttl,
            default_max_tokens=self._default_budget.max_tokens
        )

    def _make_cache_key(
        self,
        mode: SearchMode,
        query: str,
        token_budget: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成缓存键

        Args:
            mode: 检索模式
            query: 查询字符串
            token_budget: Token预算
            filters: 过滤条件

        Returns:
            缓存键
        """
        key_parts = [
            mode.value,
            query,
            str(token_budget),
            str(filters or {})
        ]
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _estimate_tokens(self, text: str) -> int:
        """
        估算文本的Token数量

        使用简单的估算方法：中文约1.5字符/token，英文约4字符/token

        Args:
            text: 输入文本

        Returns:
            估算的Token数量
        """
        if not text:
            return 0

        # 简单估算：假设混合文本平均约2字符/token
        # 对于更精确的计算，可以使用tiktoken库
        try:
            import tiktoken
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except ImportError:
            # 回退到简单估算
            chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
            other_chars = len(text) - chinese_chars
            return int(chinese_chars / 1.5 + other_chars / 4) + 1

    def _get_cached(self, cache_key: str) -> Optional[SearchContext]:
        """
        从缓存获取结果

        Args:
            cache_key: 缓存键

        Returns:
            缓存的SearchContext或None
        """
        self._cache_stats.total_requests += 1

        if cache_key in self._cache:
            context, timestamp = self._cache[cache_key]

            # 检查是否过期
            if time.time() - timestamp < self._cache_ttl:
                self._cache_stats.hits += 1
                context.cache_hit = True
                logger.debug("cache_hit", cache_key=cache_key)
                return context
            else:
                # 缓存过期，删除
                del self._cache[cache_key]
                self._cache_stats.evictions += 1

        self._cache_stats.misses += 1
        return None

    def _set_cache(self, cache_key: str, context: SearchContext):
        """
        设置缓存

        Args:
            cache_key: 缓存键
            context: 检索上下文
        """
        # 检查缓存大小限制
        if len(self._cache) >= self._cache_size:
            # 简单的LRU：删除最旧的条目
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
            self._cache_stats.evictions += 1

        self._cache[cache_key] = (context, time.time())
        logger.debug("cache_set", cache_key=cache_key)

    @property
    def cache_stats(self) -> CacheStats:
        """获取缓存统计"""
        return self._cache_stats

    async def search(
        self,
        mode: SearchMode = SearchMode.COMPREHENSIVE,
        query: str = "",
        token_budget: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> SearchContext:
        """
        统一检索入口

        Args:
            mode: 检索模式
            query: 查询字符串
            token_budget: Token预算，默认使用配置值
            filters: 过滤条件
                - project_id: 项目ID
                - file_types: 文件类型列表
                - entity_types: 实体类型列表
            context: 额外上下文

        Returns:
            SearchContext 检索结果上下文
        """
        budget = token_budget or self._default_budget.max_tokens
        filters = filters or {}

        # 生成缓存键
        cache_key = self._make_cache_key(mode, query, budget, filters)

        # 检查缓存
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.info(
                "search_cache_hit",
                mode=mode.value,
                query_length=len(query),
                token_budget=budget
            )
            return cached

        start_time = time.time()

        try:
            # 根据模式调用不同的检索方法
            if mode == SearchMode.FILES_ONLY:
                result = await self._files_only_search(query, budget, filters)
            elif mode == SearchMode.KNOWLEDGE_ONLY:
                result = await self._knowledge_only_search(query, budget, filters)
            elif mode == SearchMode.STANDARDS_ONLY:
                result = await self._standards_only_search(query, budget, filters)
            else:  # COMPREHENSIVE
                result = await self._comprehensive_search(query, budget, filters)

            # 计算总Token
            total_tokens = sum(r.token_count for r in result.contexts)
            result.total_tokens = total_tokens
            result.mode = mode

            # 设置缓存
            self._set_cache(cache_key, result)

            duration_ms = (time.time() - start_time) * 1000

            logger.info(
                "search_completed",
                mode=mode.value,
                result_count=len(result.contexts),
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                cache_hit=False
            )

            return result

        except Exception as e:
            logger.error(
                "search_failed",
                mode=mode.value,
                error=str(e),
                query=query[:100]
            )
            # 返回空结果作为降级
            return SearchContext(
                contexts=[],
                total_tokens=0,
                mode=mode,
                metadata={"error": str(e)}
            )

    async def _files_only_search(
        self,
        query: str,
        token_budget: int,
        filters: Dict[str, Any]
    ) -> SearchContext:
        """
        仅检索素材库文件

        Args:
            query: 查询字符串
            token_budget: Token预算
            filters: 过滤条件

        Returns:
            SearchContext
        """
        results: List[SearchResult] = []
        search_stats: Dict[str, Any] = {}

        try:
            # 尝试使用FileContextSelector
            if self._file_selector is None:
                self._file_selector = self._create_file_selector()

            if self._file_selector is not None:
                # 调用文件选择器
                file_results = await self._file_selector.select(
                    query=query,
                    max_tokens=token_budget,
                    project_id=filters.get("project_id"),
                    file_types=filters.get("file_types")
                )

                # 转换结果
                for fr in file_results:
                    token_count = self._estimate_tokens(fr.get("content", ""))
                    results.append(SearchResult(
                        content=fr.get("content", ""),
                        source=fr.get("source", "unknown"),
                        relevance_score=fr.get("score", 0.0),
                        token_count=token_count,
                        metadata={
                            "file_type": fr.get("file_type"),
                            "page": fr.get("page"),
                            "section": fr.get("section")
                        }
                    ))

                search_stats["file_selector"] = "used"
            else:
                # 回退到RAG检索器
                rag_results = await self._fallback_rag_search(query, token_budget, filters)
                results.extend(rag_results)
                search_stats["file_selector"] = "fallback_rag"

        except Exception as e:
            logger.error("files_only_search_failed", error=str(e))
            search_stats["error"] = str(e)

        # Token截断
        results = self._truncate_by_tokens(results, token_budget)

        return SearchContext(
            contexts=results,
            total_tokens=sum(r.token_count for r in results),
            mode=SearchMode.FILES_ONLY,
            token_allocation={"files": token_budget},
            search_stats=search_stats
        )

    async def _knowledge_only_search(
        self,
        query: str,
        token_budget: int,
        filters: Dict[str, Any]
    ) -> SearchContext:
        """
        仅检索知识图谱

        Args:
            query: 查询字符串
            token_budget: Token预算
            filters: 过滤条件

        Returns:
            SearchContext
        """
        results: List[SearchResult] = []
        search_stats: Dict[str, Any] = {}

        try:
            # 尝试使用OntologyService
            if self._ontology_service is None:
                self._ontology_service = self._create_ontology_service()

            if self._ontology_service is not None:
                # 调用知识图谱服务
                entity_types = filters.get("entity_types", ["Term", "Standard", "Process"])
                max_depth = filters.get("max_depth", 3)

                kg_results = await self._ontology_service.query(
                    query=query,
                    entity_types=entity_types,
                    max_depth=max_depth,
                    max_tokens=token_budget
                )

                # 转换并去重结果
                seen_entities = set()
                for kr in kg_results:
                    entity_id = kr.get("entity_id", "")
                    if entity_id in seen_entities:
                        continue
                    seen_entities.add(entity_id)

                    token_count = self._estimate_tokens(kr.get("content", ""))
                    results.append(SearchResult(
                        content=kr.get("content", ""),
                        source=kr.get("source", "knowledge_graph"),
                        relevance_score=kr.get("relevance", 0.0),
                        token_count=token_count,
                        entity_type=kr.get("entity_type"),
                        entity_id=entity_id,
                        relations=kr.get("relations", []),
                        metadata={
                            "node_type": kr.get("node_type"),
                            "depth": kr.get("depth", 0)
                        }
                    ))

                search_stats["ontology_service"] = "used"
                search_stats["unique_entities"] = len(seen_entities)
            else:
                search_stats["ontology_service"] = "unavailable"

        except Exception as e:
            logger.error("knowledge_only_search_failed", error=str(e))
            search_stats["error"] = str(e)

        # Token截断
        results = self._truncate_by_tokens(results, token_budget)

        return SearchContext(
            contexts=results,
            total_tokens=sum(r.token_count for r in results),
            mode=SearchMode.KNOWLEDGE_ONLY,
            token_allocation={"knowledge": token_budget},
            search_stats=search_stats
        )

    async def _standards_only_search(
        self,
        query: str,
        token_budget: int,
        filters: Dict[str, Any]
    ) -> SearchContext:
        """
        仅检索标准和规范（知识图谱中的特定类型）

        Args:
            query: 查询字符串
            token_budget: Token预算
            filters: 过滤条件

        Returns:
            SearchContext
        """
        # 限制实体类型为Standard
        standard_filters = {
            **filters,
            "entity_types": ["Standard", "Regulation", "Specification"]
        }

        return await self._knowledge_only_search(query, token_budget, standard_filters)

    async def _comprehensive_search(
        self,
        query: str,
        token_budget: int,
        filters: Dict[str, Any]
    ) -> SearchContext:
        """
        综合检索（分层注入）

        分层策略：
        - 文件层：60% Token预算
        - 知识图谱层：30% Token预算
        - 缓冲层：10% Token预算（用于补充）

        Args:
            query: 查询字符串
            token_budget: Token预算
            filters: 过滤条件

        Returns:
            SearchContext
        """
        budget = TokenBudget(token_budget)
        allocation = budget.get_allocation()

        # 并行执行检索
        files_task = self._files_only_search(
            query, allocation["files"], filters
        )
        knowledge_task = self._knowledge_only_search(
            query, allocation["knowledge"], filters
        )

        files_result, knowledge_result = await asyncio.gather(
            files_task, knowledge_task, return_exceptions=True
        )

        # 处理结果
        all_results: List[SearchResult] = []
        search_stats: Dict[str, Any] = {
            "token_allocation": allocation
        }

        # 添加文件结果
        if isinstance(files_result, SearchContext):
            all_results.extend(files_result.contexts)
            search_stats["files_count"] = len(files_result.contexts)
            search_stats["files_tokens"] = files_result.total_tokens
        else:
            search_stats["files_error"] = str(files_result)

        # 添加知识图谱结果
        if isinstance(knowledge_result, SearchContext):
            all_results.extend(knowledge_result.contexts)
            search_stats["knowledge_count"] = len(knowledge_result.contexts)
            search_stats["knowledge_tokens"] = knowledge_result.total_tokens
        else:
            search_stats["knowledge_error"] = str(knowledge_result)

        # 按相关性排序
        all_results.sort(key=lambda r: r.relevance_score, reverse=True)

        # 分层注入：高/中/低相关性
        layered_results = self._apply_layered_injection(
            all_results,
            token_budget,
            allocation
        )

        total_tokens = sum(r.token_count for r in layered_results)
        search_stats["final_count"] = len(layered_results)
        search_stats["final_tokens"] = total_tokens

        return SearchContext(
            contexts=layered_results,
            total_tokens=total_tokens,
            mode=SearchMode.COMPREHENSIVE,
            token_allocation=allocation,
            search_stats=search_stats
        )

    def _apply_layered_injection(
        self,
        results: List[SearchResult],
        total_budget: int,
        allocation: Dict[str, int]
    ) -> List[SearchResult]:
        """
        应用分层注入策略

        Layer 1: 核心上下文（高相关性，relevance_score >= 0.8）
        Layer 2: 辅助上下文（中等相关性，0.5 <= relevance_score < 0.8）
        Layer 3: 背景上下文（低相关性，relevance_score < 0.5）

        Args:
            results: 检索结果列表
            total_budget: 总Token预算
            allocation: Token分配

        Returns:
            分层后的结果列表
        """
        # 分层
        layer1 = []  # 核心上下文
        layer2 = []  # 辅助上下文
        layer3 = []  # 背景上下文

        for r in results:
            if r.relevance_score >= 0.8:
                layer1.append(r)
            elif r.relevance_score >= 0.5:
                layer2.append(r)
            else:
                layer3.append(r)

        # 按优先级添加，直到Token预算用完
        final_results: List[SearchResult] = []
        used_tokens = 0

        # Layer 1: 核心上下文（优先）
        for r in layer1:
            if used_tokens + r.token_count <= total_budget:
                final_results.append(r)
                used_tokens += r.token_count

        # Layer 2: 辅助上下文
        for r in layer2:
            if used_tokens + r.token_count <= total_budget:
                final_results.append(r)
                used_tokens += r.token_count

        # Layer 3: 背景上下文（如果有剩余预算）
        remaining_budget = total_budget - used_tokens
        if remaining_budget > 0:
            for r in layer3:
                if used_tokens + r.token_count <= total_budget:
                    final_results.append(r)
                    used_tokens += r.token_count

        return final_results

    def _truncate_by_tokens(
        self,
        results: List[SearchResult],
        max_tokens: int
    ) -> List[SearchResult]:
        """
        按Token限制截断结果

        Args:
            results: 结果列表
            max_tokens: 最大Token数

        Returns:
            截断后的结果列表
        """
        truncated: List[SearchResult] = []
        used_tokens = 0

        for r in results:
            if used_tokens + r.token_count <= max_tokens:
                truncated.append(r)
                used_tokens += r.token_count
            else:
                # 尝试截断内容
                remaining = max_tokens - used_tokens
                if remaining > 100:  # 至少保留100个token
                    # 简单截断内容
                    truncated_content = r.content[:remaining * 2]  # 粗略估算
                    truncated.append(SearchResult(
                        content=truncated_content,
                        source=r.source + " (truncated)",
                        relevance_score=r.relevance_score,
                        token_count=remaining,
                        metadata={**r.metadata, "truncated": True}
                    ))
                break

        return truncated

    def _create_file_selector(self):
        """创建文件选择器实例"""
        try:
            from app.services.context_builder import FileContextSelector
            return FileContextSelector()
        except ImportError:
            logger.debug("file_context_selector_not_available")
            return None

    def _create_ontology_service(self):
        """创建知识图谱服务实例"""
        try:
            from app.services.ontology_service import OntologyService
            return OntologyService()
        except ImportError:
            logger.debug("ontology_service_not_available")
            return None

    async def _fallback_rag_search(
        self,
        query: str,
        token_budget: int,
        filters: Dict[str, Any]
    ) -> List[SearchResult]:
        """
        回退到RAG检索

        Args:
            query: 查询字符串
            token_budget: Token预算
            filters: 过滤条件

        Returns:
            检索结果列表
        """
        results: List[SearchResult] = []

        try:
            from app.agents.core import ToolRegistry

            rag_tool = ToolRegistry.create("rag_retriever", {})
            if rag_tool is not None:
                # 调用RAG检索
                rag_result = await rag_tool.execute(query, filters)

                if rag_result.get("success"):
                    for item in rag_result.get("results", []):
                        token_count = self._estimate_tokens(item.get("content", ""))
                        results.append(SearchResult(
                            content=item.get("content", ""),
                            source=item.get("source", "rag"),
                            relevance_score=item.get("score", 0.5),
                            token_count=token_count,
                            metadata=item.get("metadata", {})
                        ))

        except Exception as e:
            logger.error("fallback_rag_search_failed", error=str(e))

        return results

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._cache_stats = CacheStats()
        logger.info("cache_cleared")

    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        return {
            "size": len(self._cache),
            "max_size": self._cache_size,
            "ttl": self._cache_ttl,
            "stats": {
                "hits": self._cache_stats.hits,
                "misses": self._cache_stats.misses,
                "hit_rate": self._cache_stats.hit_rate,
                "evictions": self._cache_stats.evictions
            }
        }
