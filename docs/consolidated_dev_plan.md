# 工艺文件辅助编辑系统 — 综合开发计划

> 合并自 `implementation_plan.md` + `code_audit_redundancy.md`
> 每个 Phase 开始前确认冗余裁定，结束后经代码审查和测试

---

## 工作流（强制执行）

```
Pre-flight（确认冗余裁定）→ Code（实施）→ Review（审查）→ Test（测试）→ Commit
```

1. **Pre-flight**: 读取本 Phase 的冗余裁定表，确认每个文件的保留/删除/修改判定
2. **Code**: 按修改文件列表实施，不改「不改什么」列表中的文件
3. **Review**: 逐项检查代码审查清单
4. **Test**: 运行验证用例
5. **Commit**: `feat(phase-N): 描述`

---

## Phase 0: 死代码清理

**目标**: 删除从未被加载和已废弃的代码
**依赖**: 无

### 冗余代码裁定

| 代码 | 裁定 | 原因 |
|------|------|------|
| `writing_agent_with_context.py` | **删除** | `discover_agents()` 从未导入，`_init_agents()` 只加载 `"writing"` |
| `review_agent_with_context.py` | **删除** | 同上，只加载 `"review"` |
| `migrate-to-github.py` | **删除** | 一次性脚本，已完成 |
| `test_intent.py` | **删除** | 开发期测试脚本 |
| `scripts/setup_kylin.sh` | **删除** | 引用不存在的 environment_kylin.yml |
| `scripts/setup_win7.bat` | **删除** | 引用不存在的 requirements-win7.txt |
| `scripts/setup_models.sh` | **删除** | 引用不存在的环境文件 |
| `services/rag_sync_service.py` | **保留** | Phase 2 用 IndexingService 替代后再删 |
| `services/__init__.py` ProfileService 注释 | **清理** | 删除残留注释和文档字符串中的 ProfileService 引用 |

### 修改文件

| 文件 | 操作 |
|------|------|
| `backend/app/agents/functional/writing_agent_with_context.py` | 删除文件 |
| `backend/app/agents/functional/review_agent_with_context.py` | 删除文件 |
| `migrate-to-github.py` | 删除文件 |
| `test_intent.py` | 删除文件 |
| `scripts/setup_kylin.sh` | 删除文件 |
| `scripts/setup_win7.bat` | 删除文件 |
| `scripts/setup_models.sh` | 删除文件 |
| `backend/app/services/__init__.py` | 清理 ProfileService 注释/文档字符串 |

### 代码审查清单

- [ ] 7 个文件已删除
- [ ] `services/__init__.py` 无 ProfileService 残留
- [ ] 无任何文件 import 被删除的模块
- [ ] `python -c "from app.agents.functional import discover_agents"` 正常
- [ ] `python main.py` 启动无报错

### 验证

```bash
# Agent 注册正常
python -c "from app.agents.functional import discover_agents; print(discover_agents())"
# 服务导入正常
python -c "from app.services import get_service_factory; print('OK')"
# 启动正常
python main.py  # Ctrl+C 确认无 import 错误
```

---

## Phase 1: 修复基础设施 — 真实 BGE Embedding

**目标**: 让 ChromaDB 存储和检索真正的语义向量
**依赖**: 无（可与 Phase 0 并行）

### 冗余代码裁定

| 代码 | 裁定 | 原因 |
|------|------|------|
| `calculate_embedding()` (context_engineering.py:147) | **保留（锚点）** | 唯一真实 embedding，调 SiliconFlow API |
| `BGEEmbeddingModel.encode_texts()` (bge_embedding.py) | **修改** | fake → 调用 `calculate_embedding()` |
| `VectorStore._generate_embeddings()` (vector_store.py) | **修改** | fake → 调用 `calculate_embedding()` |
| `BGERerankModel.rerank_results()` (bge_rerank.py) | **修改** | 降级为 identity reranker |
| `MultimodalEmbeddingService` | **保留** | 独立用途，不冲突 |
| `BGEEmbeddingModel.load_model()` | **简化** | 改为检查 API key 配置 |

### 修改文件

| 文件 | 操作 | 要点 |
|------|------|------|
| `backend/app/models/bge_embedding.py` | 修改 | `encode_texts()` 调 `calculate_embedding()` |
| `backend/app/tools/vector_store.py` | 修改 | `_generate_embeddings()` 调 `calculate_embedding()` |
| `backend/app/models/bge_rerank.py` | 修改 | 降级为 identity reranker |

### 具体改动

#### `bge_embedding.py`

```python
from app.services.context_engineering import calculate_embedding

async def encode_texts(self, texts: List[str]) -> Dict[str, Any]:
    embeddings = []
    for text in texts:
        embedding = calculate_embedding(text)
        if embedding is None:
            return {"success": False, "error": "Embedding计算失败", "error_code": "EMBEDDING_FAILED"}
        embeddings.append(embedding)
    return {
        "success": True,
        "embeddings": embeddings,
        "metadata": {"model": "bge-large-zh-v1.5", "text_count": len(texts), "embedding_dimension": len(embeddings[0]) if embeddings else 0}
    }
```

`load_model()` 简化为检查 `settings.SILICONFLOW_API_KEY` 是否配置。

#### `vector_store.py`

```python
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
async def rerank_results(self, query: str, documents: List[str]) -> Dict[str, Any]:
    n = len(documents)
    reranked_results = [
        {"document": doc, "original_index": i, "rerank_score": 1.0 - (i / max(n, 1)), "rank": i + 1}
        for i, doc in enumerate(documents)
    ]
    return {"success": True, "reranked_results": reranked_results, "metadata": {"model": "identity", "document_count": n}}
```

### 不改什么

- `context_engineering.py` — 锚点不动
- `SearchAgent` — 结构正确
- `rag_sync_service.py` — Phase 2 处理

### 代码审查清单

- [ ] `bge_embedding.py` 无 `np.random` 残留
- [ ] `vector_store.py` 无 `np.random` 残留
- [ ] 三个文件 import 链完整，无循环引用
- [ ] `calculate_embedding` 只从 `context_engineering.py` 引入
- [ ] 错误处理与原有 `calculate_embedding` 的重试逻辑一致

### 验证

```python
# 1. 确定性验证
from app.models.bge_embedding import BGEEmbeddingModel
model = BGEEmbeddingModel()
r1 = await model.encode_texts(["焊接工艺参数"])
r2 = await model.encode_texts(["焊接工艺参数"])
assert r1["embeddings"] == r2["embeddings"]  # 必须相同

# 2. 向量搜索验证
from app.tools.vector_store import VectorStore
vs = VectorStore()
await vs.add_documents(["QJ903焊接标准要求预热温度200度"], [{"source": "test"}])
results = await vs.search("焊接预热要求", top_k=1)
assert len(results) > 0
assert results[0]["content"] != ""  # 非空结果
```

---

## Phase 1.5: 路径统一

**目标**: 消除所有硬编码路径，统一到 config.py
**依赖**: 无（可与 Phase 0/1 并行）

### 冗余代码裁定

| 代码 | 裁定 | 原因 |
|------|------|------|
| `config.py` 的 `DATA_DIR` | **保留** | 指向 backend/data/ |
| `context_manager.py:65` 硬编码绝对路径 | **修改** | 改用 config 常量 |
| `api/document.py:61` `BASE_DIR.parent / "data"` | **修改** | 改用 config 常量 |
| `config.py` | **扩展** | 新增 `EXPORTS_VLM_DIR`, `EXPORTS_HTML_DIR`, `STANDARDS_DIR` |
| `test_process_document_extractor.py` 绝对路径 | **修改** | 改用 `DATA_DIR` 或 test fixture |

### 修改文件

| 文件 | 操作 |
|------|------|
| `backend/app/config.py` | 新增 `EXPORTS_VLM_DIR`, `EXPORTS_HTML_DIR`, `STANDARDS_DIR` |
| `backend/app/services/context_manager.py` | 替换硬编码路径 |
| `backend/app/api/document.py` | 统一路径引用 |
| `backend/tests/tools/test_process_document_extractor.py` | 替换绝对路径 |

### 代码审查清单

- [ ] `grep -r "D:\\\\Project" backend/` 无结果
- [ ] `grep -r "D:/ai_idea" backend/` 无结果
- [ ] 所有路径通过 `settings.XXX_DIR` 引用
- [ ] config.py 路径常量有 docstring 说明

### 验证

```bash
# 无硬编码路径
grep -rn "D:\\\\Project" backend/app/
grep -rn "D:/ai_idea" backend/
# 启动正常
python main.py
```

---

## Phase 2: 混合检索 — 结构化索引 + 向量语义搜索

**目标**: SearchAgent 同时使用精确表格索引和向量语义检索
**依赖**: Phase 1

### 冗余代码裁定

| 代码 | 裁定 | 原因 |
|------|------|------|
| `RAGSyncService` (rag_sync_service.py) | **本 Phase 后删除** | IndexingService 替代 |
| `SearchAgent._files_only_search()` | **修改** | 合并向量结果 |
| `SearchAgent._comprehensive_search()` | **修改** | 合并结构化+向量 |
| `ContextManager` | **保留** | 文件读取逻辑正确 |
| `TokenBudget` 分配比例 | **保留** | 60/30/10 结构合理 |

### 修改/新增文件

| 文件 | 操作 | 要点 |
|------|------|------|
| `backend/app/agents/search/search_agent.py` | 修改 | 新增 `_vector_search()`，合并结果 |
| `backend/app/services/indexing_service.py` | **新建** | 文档入库同步写入 ChromaDB |
| `backend/app/api/rag.py` | 修改 | 新增 `/index-document`, `/index-all`, `/search` 端点 |

### 验证

1. 入库一篇文档 → 语义查询（非精确表名）→ 命中相关表格
2. `_comprehensive_search()` 返回结构化和向量两种结果
3. WritingAgent 的 `_search_knowledge()` 拿到语义结果

---

## Phase 2.5: 依赖清理

**目标**: 删除未使用的依赖和配置
**依赖**: Phase 2 完成

### 冗余代码裁定

| 代码 | 裁定 | 原因 |
|------|------|------|
| `celery`, `redis`, `watchdog`, `pydub` | **从 environment.yml 删除** | 无 import |
| `react-beautiful-dnd` | **从 package.json 删除** | 无 import |
| `config.py` REDIS_* 配置 | **删除** | 随 celery 一起清理 |
| `QwenLLMService` (llm_service.py) | **评估后决定** | 检查是否还有调用方 |
| `DeepSeekService` | **保留** | 主 LLM 服务 |

---

## Phase 3: 统一记忆 — ChromaDB 语义检索 + 分层记忆

**目标**: 记忆系统升级为按语义相关性检索
**依赖**: Phase 1

### 冗余代码裁定

| 代码 | 裁定 | 原因 |
|------|------|------|
| `MemoryService` (memory_service.py) | **保留+扩展** | 新增 `load_relevant_memory()`，保留 `load_recent_memory()` |
| `LongTermMemory` (context_engineering.py:304) | **合并** | 增加 ChromaDB 持久化 |
| `ContextBuilder` (context_builder.py) | **保留+扩展** | 新增 `build_context_with_retrieval()` |
| `ContextSelector` (context_engineering.py:622) | **保留** | LTM 检索 + 历史选择 |
| `LLMContextService` (llm_context_service.py) | **保留** | 与 ContextBuilder 职责不同（4 层上下文 vs 任务上下文） |
| `HierarchicalContext` (hierarchical_context.py) | **保留** | JIT 检索 + 渐进式展示 |

### 修改/新增文件

| 文件 | 操作 | 要点 |
|------|------|------|
| `backend/app/services/memory_service.py` | 修改 | 新增 `load_relevant_memory(query, max_tokens)` |
| `backend/app/services/context_engineering.py` | 修改 | `LongTermMemory` 增加 ChromaDB 持久化 |
| `backend/app/services/unified_retrieval.py` | **新建** | 统一检索入口 |
| `backend/app/services/context_builder.py` | 修改 | 新增 `build_context_with_retrieval()` |

### 验证

1. Session A 保存"焊接参数"记忆 → Session B 用"焊接工艺"查询 → 命中
2. `load_recent_memory()` 仍正常（向后兼容）
3. `UnifiedRetrievalService` 返回记忆+知识+画像三类结果

---

## Phase 4: 动态用户画像

**目标**: 结构化偏好 schema + 交互学习替代3字段静态枚举
**依赖**: Phase 1，推荐 Phase 3

### 冗余代码裁定

| 代码 | 裁定 | 原因 |
|------|------|------|
| `WritingConfig` (profile.py) | **保留** | 继承扩展，不动原类 |
| `WritingPreferences` | **新建** | 继承 WritingConfig |
| `ReviewConfig` | **保留** | 当前够用 |
| `Profile.from_yaml()` / `to_yaml()` | **保留** | 保持兼容 |

### 修改/新增文件

| 文件 | 操作 | 要点 |
|------|------|------|
| `backend/app/models/profile.py` | 修改 | 新增 `WritingPreferences` dataclass |
| `backend/app/services/profile_learning.py` | **新建** | 从交互中提取偏好变化 |
| `backend/app/models/database.py` | 修改 | `UserStyleProfile` 新增列 |
| `backend/app/agents/functional/writing_agent.py` | 修改 | 注入 `WritingPreferences` |
| `backend/app/agents/orchestrator/orchestrator.py` | 修改 | 加载动态画像，触发后台学习 |

### 验证

1. 用户编辑 AI 生成内容 → `preference_schema` 学到偏好
2. 再次生成 → 反映已学到偏好
3. 新用户冷启动 → 默认值，不报错

---

## Phase 5: 旧域清理

**目标**: 清除 journalist/article 域残留
**依赖**: Phase 2.5

### 冗余代码裁定

| 代码 | 裁定 | 原因 |
|------|------|------|
| `Article` 表 / `StyleArticle` 表 | **删除** | 确认前端不再使用 |
| `api/agent.py` article_type 参数 | **修改** | 改为工艺文件相关 |
| `services/llm_service.py` (QwenLLMService) | **删除** | 无调用方 |
| `services/word_export_service.py` | **评估** | 确认是否还在使用 |
| `agents/tools/rag_retriever.py` | **删除** | 旧 RAG 检索 |
| `utils/auto_sync.py` | **删除** | 旧自动同步 |
| `models/schemas.py` | **评估** | 审计后清理 |
| `api/creation.py` | **评估** | 确认是否前端使用 |

---

## 实施顺序与并行性

```
Phase 0 ─┐
Phase 1 ─┼─ Phase 2 ─── Phase 2.5 ─── Phase 5
Phase 1.5┘      │
                └── Phase 3 ─── Phase 4
```

- Phase 0, 1, 1.5 可并行（不同文件）
- Phase 2 和 Phase 3 可并行（不同开发人员），但都依赖 Phase 1
- Phase 4 推荐 Phase 3 完成后开始
