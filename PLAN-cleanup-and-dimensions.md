# PLAN: 检索清噪 + 型号/专业维度落地（Step 0+1）

> slug: `cleanup-and-dimensions` · 关联 `ALIGN-cleanup-and-dimensions.md`
> 用户决策：物理删死文件 / C 留 stub 不放弃结构化方向 / 型号专业 LLM 推断+用户确认 / specialty 固定枚举 / filter 两层
> 范围：数据库方案 1 的 Step 0（清噪）+ Step 1（型号专业维度）。Step 2/3/4 后续单独 lead。
> seal 后不可变。Reviewer 从 git 读本文件。

## Context

调研实证：检索 6 路径是「被 2026-06-14 source-driven 重构废弃的三层检索架构（向量+图谱+关键词）」残留壳——B SearchAgent 三模式全空、D IndexingService 向量库 0 数据、E UnifiedRetrieval 0 调用方、KnowledgeGraph 写入端 0 调用，全靠 fallback 到 A HierarchicalContext 维持。真主路径是 source-driven 直注（extract 抽章节 → orchestrator 直注 task）。同时型号/专业两条穿透线完全不存在（型号无 ORM，专业 0 字段）。

本步做两件事：① 删死壳（B/D/E/KnowledgeGraph）让路径清爽，避免后续踩雷；② Material 表加 model+specialty + 检索 filter，实现型号/专业穿透。**不复活向量**（与工艺结构化方向冲突），**不补 ORM**（C 留 stub 给 Step 2 复活 F）。

## 改动清单

| 文件 | 改什么 |
|------|--------|
| **清噪 - 删文件** | 物理删：`agents/search/search_agent.py`、`services/indexing_service.py`、`services/unified_retrieval.py`、`services/knowledge_graph.py`、`tools/vector_store.py`、`api/rag.py` |
| **清噪 - 改调用方** | `writing_agent.py:148` `_search_knowledge` 删 SearchAgent 调用，改走 `preloaded_content`/HierarchicalContext；grep 全仓清 `import search_agent/indexing_service/unified_retrieval/knowledge_graph/vector_store` 的残留引用 |
| **C 留 stub** | `services/knowledge_search.py` 改成不 ImportError 的占位（注释 MaterialCatalog/ProcessStep/Standard ORM 引用，函数签名留，body 返回空 + 注释「Step 2 复活 F 时补 ORM」）；`api/knowledge.py` 死端点标 deprecated 或删 |
| **Material 加字段** | `models/database.py:50 Material` 加 `model = Column(String(255), nullable=True)` + `specialty = Column(String(50), nullable=True)`；加迁移（SQLite ALTER TABLE materials ADD COLUMN ...） |
| **上传 LLM 推断型号专业** | 上传 API（`api/agent.py`/`creation.py` 上传端点）：解析完文档名/封面后，调 LLM 推断 model+specialty，写入 Material 行（用户可在前端确认/改） |
| **前端字段** | 上传 UI（`frontend/src/`）加 specialty 下拉（固定枚举）+ model 输入框，LLM 预填 + 用户确认 |
| **filter 两层** | `hierarchical_context.py`：`_get_all_documents:164`（db.query:187 加 `.filter(Material.specialty == ...)` if filter 传了）+ `_build_doc_dict:224` 注入 model/specialty 到 doc dict；`search_tables:363` + `global_keyword_search:737` 签名加 `filters: Dict` 参数，按 doc.model/specialty 早返回。orchestrator 直注路径透传 filter |
| **CLAUDE.md 技术栈** | 去 ChromaDB / BGE-Embedding / BGE-Rerank（向量层确认放弃） |

## specialty 固定枚举

```
assembly(装配) / welding(焊接) / coating(涂覆/表面处理) / machining(机加)
inspection(检验) / heat_treatment(热处理) / general(通用)
```
存字符串值（如 "assembly"），前端下拉显示中文 label。

## 禁区

- ❌ Step 2 复活 F（KnowledgeExtractor/StandardExtractor 接上传管线）—— 下一 lead
- ❌ Step 3 画像扩全章节 + triples 清洗 + ConditionGroup —— 下一 lead
- ❌ Step 4 标准强约束 —— 下一 lead
- ❌ 复活向量检索（D 已确认删，不重新接）
- ❌ 补 MaterialCatalog/ProcessStep/Standard ORM（C 留 stub，ORM 是 Step 2 的事）
- ❌ 重写 HierarchicalContext 主逻辑（只加 filter，不动检索算法）

## 验证

1. **清噪不破坏**：`pytest tests/` 全量 0 failed（SearchAgent 等删后，import 不挂、writing_agent 主路径仍走）
2. **C stub 不 ImportError**：`python -c "from app.services.knowledge_search import KnowledgeSearchService"` 不挂
3. **Material 字段**：迁移后 `materials` 表有 model/specialty 列；上传能写
4. **filter 穿透**：构造 2 个 Material（不同 specialty），HierarchicalContext 传 `filters={"specialty":"welding"}` 只返回 welding 的文档（单测）
5. **LLM 推断**：上传一个文档，LLM 推断 model/specialty 写入 Material（抽查）

```bash
cd backend && /c/Users/alerl/.conda/envs/gywj/python.exe -m pytest tests/ -c pytest.ini --rootdir . --tb=short -q
# 穿透单测：tests/test_hierarchical_context_filters.py（新建）
```

## 拆分（执行 loop 节点）

1. **节点1 清噪**：删 B/D/E/KnowledgeGraph 文件 + api/rag.py + 改 writing_agent.py:148 调用 + 清残留 import + C stub + api/knowledge.py 死端点
2. **节点2 Material 字段 + 迁移**：database.py 加 model/specialty + ALTER TABLE 迁移
3. **节点3 上传 LLM 推断型号专业**：上传 API 加 LLM 推断 + 写 Material（后端）
4. **节点4 filter 两层**：HierarchicalContext `_get_all_documents` + `search_tables`/`global_keyword_search` 加 filter + orchestrator 透传
5. **节点5 前端字段 + CLAUDE.md 改**：上传 UI specialty 下拉 + model 输入（LLM 预填）+ CLAUDE.md 去向量技术栈
6. **节点6 验证**：pytest 回归 + 穿透单测 + LLM 推断抽查
