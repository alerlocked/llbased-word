# 需求对齐卡：复活 F 结构化抽取落库（Step 2）

> slug: `revive-extract-funnel`
> 关联：[[exp-retrieval-cleanup-and-dimensions]]（F 设计意图 + 烂尾原因）、PLAN-cleanup-and-dimensions（Step 0 留了 C stub 等本步）
> 范围：数据库方案 Step 2。后续 Step 3（画像扩全章节 + triples 清洗）/ Step 4（标准 review 校验）单独 lead。

## 目标

- **解决谁的什么问题**：F（KnowledgeExtractor/StandardExtractor）实现完但触发链断——上传管线（document_processor）不自动调 → material_catalog/process_steps/standards 表空 → C KnowledgeSearchService 查空 → ConditionGroup 无数据源 → 「准确找到具体文件内容」+「画像学习注入」+「标准严约束」全卡这。
- **成功长什么样**（可观察）：
  1. 上传一份工艺文档（如 documents/1）→ 解析后自动抽物料/工序落 material_catalog/process_steps（行数 > 0）
  2. C KnowledgeSearchService 去 stub，查询返回真实数据（不空、不 ImportError）
  3. 标准文档（QJ903）上传 → StandardExtractor 抽条款落 standards/standard_clauses
  4. 落库时带 model/specialty 维度（Step 1 的穿透能用上）
  5. pytest 全量回归不引入新 fail

## 边界

### 做
- **补 ORM**：MaterialCatalog / ProcessStep / Standard / StandardClause / StepTool / StepMaterial（对应 craftdoc.db 已有表，对齐 schema）
- **接 KnowledgeExtractor**：document_processor.process_document 解析完成后调 `extract_and_save`（物料/工序落库）
- **接 StandardExtractor**：标准文档上传 → 调 standard_extract（条款落库）
- **C 恢复**：knowledge_search.py 去 stub（恢复 ORM import + 真查询）；api/knowledge.py 死端点复活或重新评估
- **落库带维度**：MaterialCatalog/ProcessStep 关联 Material 的 model/specialty（或表自带维度列），让结构化查询也支持穿透

### 不做
- ❌ Step 3 画像扩全章节 + triples 清洗 + ConditionGroup 注入 —— 下一 lead（依赖本步落库数据）
- ❌ Step 4 标准强约束（StandardExtractor 注入 + review 校验）—— 下一 lead
- ❌ 重写 KnowledgeExtractor/StandardExtractor（实现完，只接触发链）
- ❌ 改 source-driven 主路径（extract 抽章节直注不动）
- ❌ 改前端（上传自动落库，无需前端配合）

## 模糊点（已清零，2026-07-05 对齐）

1. **补 ORM 范围**：✅ **全 6 个**（MaterialCatalog/ProcessStep/Standard/StandardClause/StepTool/StepMaterial）
2. **触发方式**：✅ **try-except 不阻塞**——document_processor 解析完成后调 extract_and_save，失败记日志不影响解析响应。理由：**素材库 PDF 解析不并发**（用户定），不需要异步队列；并发需求在其他任务（对话栏 PDF/对话路径），不在本步范围，留后续架构优化
3. **标准文档**：✅ **复用上传 + 类型判别**（检测 QJ903 标准 → StandardExtractor）
4. **维度关联**：✅ **表自带列**——MaterialCatalog（已有 model 列）+ ProcessStep 加 specialty 列，落库时从 Material 带，查询直接按表过滤（少 JOIN）
5. **extract_from_doc 数据源**：✅ PlanMode 确认（读 content.html/chapter_index 表格）

→ 模糊点清零，进 PlanMode 写 PLAN。

## 下游

- → `PLAN-revive-extract-funnel.md`（同 slug，模糊点清零后进 PlanMode）
