# 工艺文件辅助编辑系统 — 代码实施计划

## Context

项目已有完整的 agent 框架和前端界面，但存在四个核心技术债：
1. ChromaDB/BGE 全是 fake embedding（`np.random.rand(1024)`），向量检索完全不可用
2. 只有结构化索引查表，没有语义检索能力（RAG 模块已 deprecated）
3. 记忆系统是 markdown 文件按时间排序加载，无语义检索，无法跨会话复用
4. 用户画像是3个静态枚举字段，不从交互中学习

本项目唯一真正工作的 embedding 在 `context_engineering.py` 的 `calculate_embedding()`，调用 SiliconFlow API（BAAI/bge-large-zh-v1.5）。所有修改以此为锚点。

---

## Phase 1：修复基础设施 — 真实 BGE Embedding

**目标**：让 ChromaDB 存储和检索真正的语义向量

### 修改文件

| 文件 | 操作 | 要点 |
|------|------|------|
| `backend/app/models/bge_embedding.py` | 修改 | `encode_texts()` 调用 `calculate_embedding()` 替换 `np.random.rand()` |
| `backend/app/tools/vector_store.py` | 修改 | `_generate_embeddings()` 调用 `calculate_embedding()` 替换 `np.random.rand()` |
| `backend/app/models/bge_rerank.py` | 修改 | 降级为 identity reranker（按原始顺序归一化分数），不阻塞主流程 |

### 关键细节

- **锚点函数**：`backend/app/services/context_engineering.py` 的 `calculate_embedding(text)` 是唯一可用的 embedding 路径，已有重试和错误处理
- 两个文件都 import `calculate_embedding`，不再各自实现
- `load_model()` 简化为检查 SiliconFlow API key 是否配置

### 具体改动

#### `bge_embedding.py`

```python
# 修改 encode_texts() 方法：
from app.services.context_engineering import calculate_embedding

async def encode_texts(self, texts: List[str]) -> Dict[str, Any]:
    embeddings = []
    for text in texts:
        embedding = calculate_embedding(text)
        if embedding is None:
            return {"success": False, "error": "Embedding计算失败", "error_code": "EMBEDDING_FAILED"}
        embeddings.append(embedding)

    result = {
        "success": True,
        "embeddings": embeddings,
        "metadata": {
            "model": "bge-large-zh-v1.5",
            "text_count": len(texts),
            "embedding_dimension": len(embeddings[0]) if embeddings else 0,
        }
    }
    return result
```

- `load_model()` 简化为检查 `settings.SILICONFLOW_API_KEY` 是否配置，不再假装加载本地模型

#### `vector_store.py`

```python
# 修改 _generate_embeddings() 方法：
from app.services.context_engineering import calculate_embedding

async def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
    embeddings = []
    for text in texts:
        embedding = calculate_embedding(text)
        if embedding is None:
            raise RuntimeError(f"Embedding计算失败: {text[:50]}")
        embeddings.append(embedding)
    return embeddings
```

#### `bge_rerank.py`

```python
# 降级为 identity reranker
async def rerank_results(self, query: str, documents: List[str]) -> Dict[str, Any]:
    # Identity reranker: 按原始顺序归一化分数
    n = len(documents)
    reranked_results = []
    for i, doc in enumerate(documents):
        score = 1.0 - (i / max(n, 1))
        reranked_results.append({
            "document": doc,
            "original_index": i,
            "rerank_score": score,
            "rank": i + 1
        })
    return {"success": True, "reranked_results": reranked_results, "metadata": {...}}
```

### 不改什么
- `context_engineering.py` — 不动，它是锚点
- `SearchAgent` — 结构正确，不需要改
- `rag_sync_service.py` — 已走 SiliconFlow API，不用动

### 验证
1. 调用 `VectorStore.add_documents()` 存入样本文本，确认 embedding 非 random
2. 调用 `VectorStore.search()` 做语义查询，确认结果按相似度排序
3. 相同文本两次 encode 得到相同向量（确定性验证）

---

## Phase 2：混合检索 — 结构化索引 + 向量语义搜索

**目标**：SearchAgent 同时使用精确表格索引和向量语义检索

**依赖**：Phase 1 完成

### 修改/新增文件

| 文件 | 操作 | 要点 |
|------|------|------|
| `backend/app/agents/search/search_agent.py` | 修改 | 新增 `_vector_search()` 方法，在 `_files_only_search()` 和 `_comprehensive_search()` 中合并结构化+向量结果 |
| `backend/app/services/indexing_service.py` | **新建** | 文档入库时同步写入 ChromaDB（表格+文本块），替代 deprecated 的 RAGSyncService |
| `backend/app/api/rag.py` | 修改 | 新增 `/index-document`、`/index-all`、`/search` 端点 |

### 关键细节

- `_vector_search()`：调用 `VectorStore.search()`，返回 `SearchResult` 列表
- 合并策略：结构化结果优先（精确匹配分高），向量结果补充（语义关联）
- 去重：按内容 hash 去重，避免同一表格出现两次
- `IndexingService`：读取 `exports_vlm_full/` 下的 JSON 索引，将每个表格和文本块写入 ChromaDB，metadata 包含 source/doc_name/table_id

### 不改什么
- `ContextManager` — 文件读取逻辑正确不动
- `TokenBudget` 分配比例 — 已有的 60/30/10 结构合理
- `MemoryService` — Phase 3 再改

### 验证
1. 入库一篇文档，用语义查询（非精确表名）搜索，验证能找到相关表格
2. `_comprehensive_search()` 返回结构化和向量两种结果
3. WritingAgent 的 `_search_knowledge()` 能拿到有用的语义结果

---

## Phase 3：统一记忆 — ChromaDB 语义检索 + 分层记忆

**目标**：记忆系统从"按时间取最近 N 个文件"升级为"按语义相关性检索"

**依赖**：Phase 1 完成。Phase 2 非必须但推荐。

### 修改/新增文件

| 文件 | 操作 | 要点 |
|------|------|------|
| `backend/app/services/memory_service.py` | 修改 | 新增 `load_relevant_memory(query, max_tokens)` 方法，用 ChromaDB 做语义检索；保留 `load_recent_memory()` 不动 |
| `backend/app/services/context_engineering.py` | 修改 | `LongTermMemory` 类增加 ChromaDB 持久化（内存列表做 L1 缓存） |
| `backend/app/services/unified_retrieval.py` | **新建** | 统一检索入口：同时查记忆、知识库、用户画像，返回合并结果 |
| `backend/app/services/context_builder.py` | 修改 | 新增 `build_context_with_retrieval()` 方法，调用 UnifiedRetrievalService |

### 关键细节

- 记忆存储双写：markdown 文件（主存） + ChromaDB（索引），不删除原有机制
- ChromaDB 用独立 collection：`memory_store`（与 `process_knowledge` 分离）
- `load_relevant_memory(query)` 是新主接口，`load_recent_memory()` 保留做 fallback
- `UnifiedRetrievalService.retrieve(query, context_type)`：context_type 支持 "memory"/"knowledge"/"profile"/"all"
- 用户画像数据也写入 ChromaDB（`user_profiles` collection），统一检索

### 不改什么
- `ContextManager` — 文件读取逻辑正确不动
- `BaseAgent` / `AgentRegistry` — agent 框架不动
- markdown 文件存储 — 保留为主存储，ChromaDB 为辅助索引

### 验证
1. Session A 保存一条关于"焊接参数"的记忆 → Session B 用"焊接工艺"查询 → 命中 Session A 的记忆
2. `load_recent_memory()` 仍然正常工作（向后兼容）
3. `UnifiedRetrievalService` 同时返回记忆+知识+画像三类结果

---

## Phase 4：动态用户画像 — 从交互中学习的偏好模型

**目标**：用结构化偏好 schema + 交互学习替代3字段静态枚举

**依赖**：Phase 1 完成。Phase 3 推荐完成。

### 修改/新增文件

| 文件 | 操作 | 要点 |
|------|------|------|
| `backend/app/models/profile.py` | 修改 | 新增 `WritingPreferences` dataclass，扩展 `WritingConfig`，增加可学习维度和置信度 |
| `backend/app/services/profile_learning.py` | **新建** | 从用户编辑、反馈、参考文章中提取偏好变化，更新画像 |
| `backend/app/models/database.py` | 修改 | `UserStyleProfile` 表新增 `preference_schema`（JSON）、`interaction_count` 列；新增 `PreferenceUpdateLog` 表 |
| `backend/app/agents/functional/writing_agent.py` | 修改 | `_do_edit()`/`_do_generate()` 注入 `WritingPreferences`；`handle_feedback()` 触发画像学习 |
| `backend/app/agents/orchestrator/orchestrator.py` | 修改 | 会话初始化加载动态画像，传给功能 Agent；每次交互后触发后台画像学习 |

### 关键细节

- `WritingPreferences` 扩展维度：sentence_style、paragraph_length、use_passive_voice、preferred_connectors、avoid_phrases，每维带 confidence
- `ProfileLearningService.learn_from_edit(original, edited)`：用 LLM 分析用户改了什么、为什么改，提取偏好变化
- 画像学习**异步执行**，不阻塞用户操作
- `WritingPreferences.to_prompt_injection()`：只有 confidence > 阈值的维度才注入 prompt
- 冷启动：新用户使用默认 `WritingConfig` 值，逐步学习替换

### 不改什么
- `WritingConfig` 类 — 保留不动，太多地方引用，`WritingPreferences` 继承扩展
- `ReviewConfig` — 当前够用
- `Profile.from_yaml()` / `Profile.to_yaml()` — 保持兼容

### 验证
1. 用户编辑 AI 生成内容（如改成更简洁风格） → 检查 `preference_schema` 是否学到 "concise"
2. 再次生成 → AI 输出反映已学到的偏好
3. 新用户冷启动 → 使用默认值，不报错
4. `StyleLearningLog` 表继续正常写入（向后兼容）

---

## 实施时间线

| 阶段 | 周期 | 前置依赖 |
|------|------|----------|
| Phase 1 | 第1-2周 | 无 |
| Phase 2 | 第3-4周 | Phase 1 |
| Phase 3 | 第5-7周 | Phase 1 |
| Phase 4 | 第8-10周 | Phase 1，推荐 Phase 3 |

Phase 2 和 Phase 3 可并行（不同开发人员）。

## 风险控制

1. **SiliconFlow API 限流**：`calculate_embedding()` 已有指数退避重试。批量入库（Phase 2）加限速器（10 req/s）
2. **ChromaDB collection 隔离**：`process_knowledge`（文档）、`memory_store`（记忆）、`user_profiles`（画像）分开
3. **向后兼容**：所有改动遵循"新增不替换"原则，原有接口保持可用
4. **性能**：ChromaDB HNSW 索引在 <100K 文档规模下查询 <100ms，项目数据量远低于此

## 当前代码状态摘要（已读文件）

### 已确认存在的问题

1. **`bge_embedding.py:132`** — `np.random.rand(self.embedding_dimension).tolist()` 生成随机向量
2. **`vector_store.py:287`** — `np.random.rand(1024).tolist()` 生成随机向量
3. **`bge_rerank.py:139`** — 线性递减分数模拟重排序
4. **`context_engineering.py:147`** — `calculate_embedding()` 是唯一可用的真实 embedding（SiliconFlow API）
5. **`memory_service.py:83`** — `load_recent_memory()` 按文件修改时间加载，无语义检索
6. **`profile.py:14-33`** — `WritingConfig` 只有 tone/terminology/detail_level 三个静态字段
7. **`database.py:127-139`** — `UserStyleProfile` 表无 preference_schema 和 interaction_count

### 项目路径
- 项目根目录：`D:/Project Nantianmen/projects/localknowledgebase-word/`
- 后端代码：`D:/Project Nantianmen/projects/localknowledgebase-word/backend/app/`
- Conda 环境：`gywj`
