# 代码冗余与路径审计报告

审计日期：2026-04-16

---

## 一、多版本并存（同一功能多个实现）

### 1.1 Embedding — 三套并存，只有一套能用

| 实现 | 文件 | 状态 |
|------|------|------|
| `calculate_embedding()` | `services/context_engineering.py:147` | **唯一可用**，调 SiliconFlow API |
| `BGEEmbeddingModel.encode_texts()` | `models/bge_embedding.py:93` | **假实现**，`np.random.rand(1024)` |
| `VectorStore._generate_embeddings()` | `tools/vector_store.py:268` | **假实现**，`np.random.rand(1024)` |
| `MultimodalEmbeddingService` | `services/multimodal_embedding_service.py` | 独立用途（图文混合），不确定是否真实 |

**问题**：`BGEEmbeddingModel` 和 `VectorStore._generate_embeddings` 都声称用 BGE 模型，实际生成随机向量。任何依赖这两个方法的检索都是无效的。

### 1.2 上下文构建 — 五层并存

| 实现 | 文件 | 职责 |
|------|------|------|
| `ContextManager` | `services/context_manager.py` | 从 exports_vlm_full 读 JSON，提供表格数据 |
| `ContextBuilder` | `services/context_builder.py` | 组装任务信息+对话历史+文档 |
| `ContextSelector` | `services/context_engineering.py:622` | LTM 检索 + 历史选择 + 工具子集 |
| `HierarchicalContext` | `services/hierarchical_context.py` | JIT 检索 + 渐进式展示 |
| `LLMContextService` | `services/llm_context_service.py` | 4 层上下文（画像+模板+检索+系统） |

**问题**：`ContextBuilder` 和 `LLMContextService` 功能高度重叠。orchestrator 里 `_load_profile_context` 用 `ContextService`，`_build_retrieval_context` 用 `HierarchicalContext`，两套互不关联。

### 1.3 Agent — writing/review 各两个版本

| 版本 | 文件 | 注册名 |
|------|------|--------|
| `WritingAgent` | `agents/functional/writing_agent.py` | `"writing"` |
| `WritingAgentWithContext` | `agents/functional/writing_agent_with_context.py` | `"writing_with_context"` |
| `ReviewAgent` | `agents/functional/review_agent.py` | `"review"` |
| `ReviewAgentWithContext` | `agents/functional/review_agent_with_context.py` | `"review_with_context"` |

**问题**：`_with_context` 版本是扩展版，集成了 `ContextService`。但 `__init__.py` 的 `discover_agents()` 只导入 `writing_agent`、`proofread_agent`、`review_agent`（无 _with_context），orchestrator 的 `_init_agents()` 也只加载 `["writing", "proofread", "review"]`。**`_with_context` 版本从未被加载，是死代码。**

### 1.4 记忆系统 — 两个独立实现

| 实现 | 文件 | 存储 |
|------|------|------|
| `MemoryService` | `services/memory_service.py` | markdown 文件，按时间排序 |
| `LongTermMemory` | `services/context_engineering.py:304` | 内存列表 + embedding |

**问题**：两套记忆完全独立，无互通。`MemoryService` 被服务层使用，`LongTermMemory` 被 `ContextSelector` 使用。

### 1.5 服务注册 — ProfileService 已删但残留

- `services/__init__.py:30` 注释：`# ProfileService 已删除，功能合并到 ContextService`
- `services/__init__.py:48` 注释：`# 'ProfileService' - 已删除`
- `services/__init__.py:11` 文档字符串仍写：`- profile_service: 用户画像管理服务`

---

## 二、硬编码路径

### 2.1 绝对路径（必须修复）

| 文件 | 行号 | 内容 |
|------|------|------|
| `services/context_manager.py` | 65 | `data_dir = r"D:\Project Nantianmen\projects\localknowledgebase-word\data\exports_vlm_full"` |
| `data/pdf_queue_state.json` | 5-19 | `D:\Project Nantianmen\...` 序列化的路径 |
| `scripts/convert_standards_to_exports.py` | 8 | `Set-Location D:/Project Nantianmen/...` |
| `backend/tests/tools/test_process_document_extractor.py` | 23,54,83,138 | `D:/ai_idea/localknowledgebase-word/...`（**连旧项目路径都没改**） |

### 2.2 路径策略不统一

| 路径引用方式 | 使用位置 |
|-------------|---------|
| `settings.DATA_DIR / "..."` | config.py, 多数服务 |
| `settings.BASE_DIR.parent / "data"` | api/document.py（绕到项目根的 data/） |
| 硬编码相对路径 `Path("data/exports_vlm_full")` | scripts/*.py |
| 硬编码绝对路径 | context_manager.py, tests |

**关键矛盾**：`config.py` 定义 `DATA_DIR = BASE_DIR / "data"` 指向 `backend/data/`，但实际文档数据在项目根的 `data/exports_vlm_full/`。`api/document.py:61` 用 `settings.BASE_DIR.parent / "data"` 绕路，`context_manager.py` 直接硬编码绝对路径。

### 2.3 data/ 目录分裂

```
项目根/data/exports_vlm_full/    ← 实际文档数据（JSON 索引）
项目根/data/exports_html/        ← 生成的 HTML
项目根/data/standards_parsed/    ← 标准解析结果

backend/data/                    ← config.DATA_DIR 指向这里
backend/data/database/           ← SQLite 数据库
backend/data/uploads/            ← 上传文件
backend/data/tasks/              ← 任务 JSON
backend/data/vector_store/       ← ChromaDB 持久化
```

两个 `data/` 目录并存，没有统一约定。

---

## 三、遗留旧项目代码

### 3.1 journalist/article 域残留（15 个文件）

从旧项目（新闻/稿件系统）迁移来，未清理干净：

| 文件 | 残留内容 |
|------|---------|
| `models/database.py` | `Article` 表、`article_type` 字段、`StyleArticle` 表 |
| `api/agent.py` | `article_type: str = "general"` 参数 |
| `api/creation.py` | 稿件相关接口 |
| `services/llm_service.py` | QwenLLMService，可能是旧版 LLM 调用 |
| `services/rag_sync_service.py` | `sync_all_articles()` 方法 |
| `services/word_export_service.py` | 稿件导出 |
| `agents/tools/rag_retriever.py` | 旧 RAG 检索工具 |
| `utils/auto_sync.py` | 旧自动同步逻辑 |
| `models/schemas.py` | 旧 schema 定义 |
| `models/__init__.py` | 导出旧模型 |

### 3.2 已标记 deprecated 但仍存在

| 文件 | 标记 |
|------|------|
| `services/rag_sync_service.py` | `warnings.warn("RAGSyncService 已弃用")`，`ENABLE_RAG = false` |
| `services/context_engineering.py:134` | `_get_embedding_service()` 注释"已废弃" |

### 3.3 根目录遗留文件

| 文件 | 判定 |
|------|------|
| `migrate-to-github.py` | **一次性脚本**，已确认用 git 管理，可删 |
| `test_intent.py` | **开发期测试脚本**，可移入 tests/ 或删除 |
| `scripts/setup_kylin.sh` | **Kylin 兼容脚本**，引用不存在的 `environment_kylin.yml` |
| `scripts/setup_win7.bat` | **Win7 兼容脚本**，引用不存在的 `requirements-win7.txt` |
| `scripts/setup_models.sh` | **模型安装脚本**，引用不存在的环境文件 |

### 3.4 未使用的依赖

**后端（environment.yml）：**
- `celery==5.3.4` — 无 import
- `redis==5.0.1` — 无 import
- `watchdog==6.0.0` — 无 import
- `pydub==0.25.1` — 无 import

**前端（package.json）：**
- `react-beautiful-dnd` — 无 import

---

## 四、配置重复

### 4.1 两个 config 文件

| 文件 | 用途 |
|------|------|
| `backend/app/config.py` | 主配置，pydantic Settings |
| `backend/app/shared/config.py` | 共享配置，import 式 |

### 4.2 LLM 服务重复

| 服务 | 文件 | 用途 |
|------|------|------|
| `DeepSeekService` | `services/deepseek_service.py` | DeepSeek API |
| `QwenLLMService` | `services/llm_service.py` | 通义千问（旧版） |
| `ContextService` 中也有 LLM 调用 | `services/context_service.py` | 模板/画像 |

orchestrator 的 `_generate_modification_plan` 优先用 DeepSeek，回退到 Qwen。

### 4.3 Redis 配置存在但未使用

`config.py:39-42` 定义了 `REDIS_HOST/PORT/DB/URL`，配合 `celery` 使用。但 celery 和 redis 都没有实际使用。

---

## 五、建议清理优先级

### P0 — 影响正确性（在 Phase 1 实施时一起修）

| 项目 | 操作 |
|------|------|
| `context_manager.py:65` 硬编码绝对路径 | 改用 `settings.BASE_DIR.parent / "data" / "exports_vlm_full"` |
| `vector_store.py` fake embedding | Phase 1 修 |
| `bge_embedding.py` fake embedding | Phase 1 修 |

### P1 — 死代码清理（不影响功能）

| 项目 | 操作 |
|------|------|
| `rag_sync_service.py` | 整个文件标记 deprecated，Phase 2 用 IndexingService 替代后删除 |
| `writing_agent_with_context.py` | 从未被加载，删除或合并到 writing_agent |
| `review_agent_with_context.py` | 从未被加载，删除或合并到 review_agent |
| `migrate-to-github.py` | 删除 |
| `scripts/setup_kylin.sh`, `setup_win7.bat`, `setup_models.sh` | 删除（引用不存在的文件） |
| `test_intent.py` | 移入 tests/ 或删除 |

### P2 — 路径统一

| 项目 | 操作 |
|------|------|
| 定义 `EXPORTS_VLM_DIR` 和 `EXPORTS_HTML_DIR` 到 config.py | 统一指向项目根的 `data/` |
| `context_manager.py` 默认路径 | 改用 config 常量 |
| `test_process_document_extractor.py` 绝对路径 | 改用项目相对路径或 test fixture |
| `data/pdf_queue_state.json` 中的绝对路径 | 清理后重新生成 |

### P3 — 依赖清理

| 项目 | 操作 |
|------|------|
| environment.yml 删除 celery, redis, watchdog, pydub | `pip list` 确认无依赖后删除 |
| package.json 删除 react-beautiful-dnd | 确认无依赖后删除 |
| config.py 删除 REDIS_* 和 CELERY 相关配置 | 随 celery 一起删除 |

### P4 — 旧域清理（低优先级）

| 项目 | 操作 |
|------|------|
| `Article` 表 / `StyleArticle` 表 | 确认前端不再使用后删除 |
| `api/agent.py` 中 `article_type` 参数 | 改为工艺文件相关 |
| `services/__init__.py` 中 ProfileService 注释和文档 | 清理 |
| `models/schemas.py` 旧 schema | 审计后清理 |
