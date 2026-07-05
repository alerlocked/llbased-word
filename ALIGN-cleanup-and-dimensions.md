# 需求对齐卡：检索清噪 + 型号/专业维度落地（Step 0+1）

> slug: `cleanup-and-dimensions`
> 关联：3 轮 agent 调研（检索路径全景 / 画像注入 / 设计意图+历史），已落 [[exp-derive-strong-node]] [[exp-test-isolation-global-state]]
> 范围：数据库方案 1 的前两步（清噪 + 维度）。Step 2/3/4（F 复活 / 画像扩全章节 / 标准强约束）后续单独 lead。

## 目标

- **解决谁的什么问题**：检索路径 6 条太乱（B/D/E/F 死壳残留，靠 fallback 维持）；型号/专业两条穿透线完全不存在（型号无 ORM，专业 0 字段）。
- **成功长什么样**（可观察）：
  1. 检索路径清爽——死壳删干净，writing_agent 主路径不再调空壳 SearchAgent
  2. Material 表有 model + specialty 字段，上传能标
  3. HierarchicalContext 检索能按 model/specialty 过滤（穿透验证：传 model=X 只返回 X 的文档）
  4. pytest 全量回归 0 failed（清噪不破坏现有）

## 边界

### 做
**Step 0 清噪**：
- 删 B（SearchAgent）/ D（IndexingService+vector_store）/ E（UnifiedRetrieval）/ KnowledgeGraph 的死壳
- 改 writing_agent.py:148（不调 SearchAgent，直接走 preloaded/HierarchicalContext）
- 删/改 api/rag.py + api/knowledge.py 的死端点（ImportError 的）
- 改 CLAUDE.md 技术栈（去 ChromaDB/BGE/Rerank）

**Step 1 型号/专业维度**：
- Material 表加 `model` + `specialty` 列（迁移）
- 上传时标型号/专业（后端 API + 前端字段）
- HierarchicalContext（+ orchestrator 直注路径）加 model/specialty filter

### 不做
- ❌ Step 2 复活 F（KnowledgeExtractor/StandardExtractor 接上传管线）—— 下一 lead
- ❌ Step 3 画像扩全章节 + triples 清洗 + ConditionGroup —— 下一 lead
- ❌ Step 4 标准强约束（StandardExtractor 注入 + review 校验）—— 下一 lead
- ❌ 改向量检索（已确认删，不复活）
- ❌ 重写 HierarchicalContext（只加 filter，不动主逻辑）

## 模糊点（已清零，2026-07-05 对齐）

1. **清噪范围**：✅ **物理删文件**（SearchAgent/IndexingService/UnifiedRetrieval/KnowledgeGraph + 对应 api 端点 + vector_store），git 历史可回溯
2. **C + material_catalog**：✅ **留 stub**——C KnowledgeSearchService 改成不 ImportError 的占位（注释「Step 2 复活 F 时补 ORM」），material_catalog 表留着不删。不放弃结构化方向，但这次不补 ORM
3. **型号/专业字段来源**：✅ **LLM 推断 + 用户确认**——上传时 LLM 从文档名/封面推断 model+specialty 预填前端，用户确认/修改
4. **specialty 取值**：✅ **固定枚举**：`assembly`(装配) / `welding`(焊接) / `coating`(涂覆/表面处理) / `machining`(机加) / `inspection`(检验) / `heat_treatment`(热处理) / `general`(通用)
5. **filter 层**：✅ 两层——`HierarchicalContext._get_all_documents`（按 Material.model/specialty 过滤文档列表，最早最省）+ `search_tables`/`global_keyword_search`（细粒度 filter 透传）
6. **CLAUDE.md 技术栈**：✅ 去 ChromaDB/BGE-Embedding/BGE-Rerank（向量层确认放弃）

→ 模糊点清零，进 PlanMode 写 PLAN。

## 下游

- → `PLAN-cleanup-and-dimensions.md`（同 slug，模糊点清零后进 PlanMode）
