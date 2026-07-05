# PLAN: 复活 F 结构化抽取落库（Step 2）

> slug: `revive-extract-funnel` · 关联 `ALIGN-revive-extract-funnel.md`、[[exp-retrieval-cleanup-and-dimensions]]
> 用户决策：补全 6 ORM / try-except 不阻塞触发（素材库不并发）/ 标准文档复用上传+类型判别 / 表自带维度列
> 范围：数据库方案 Step 2。Step 3/4 后续单独 lead。
> seal 后不可变。Reviewer 从 git 读本文件。

## Context

F（KnowledgeExtractor + StandardExtractor）实现完但触发链断：① 6 ORM（MaterialCatalog/ProcessStep/Standard/StandardClause/StepMaterial/StepTool）从未定义 → extract_and_save ImportError；② document_processor 上传解析不自动调 → 表空；③ C knowledge_search 被 Step 0 改成 stub。本步复活整条链：补 ORM → document_processor 解析后触发 → C 去 stub 恢复。素材库不并发（try-except 够）。

## 改动清单

| 文件 | 改什么 |
|------|--------|
| **`app/models/database.py`**（:369 后） | 补 6 ORM 对齐 craftdoc.db：`MaterialCatalog`（id/category/name/brand/model/standard_code/spec/unit/source_doc/created_at + **specialty**）/ `ProcessStep`（id/doc_id/step_name/step_order/parent_step_id/description/created_at + **specialty**）/ `Standard`（id/code/title/category/content_json/created_at）/ `StandardClause`（id/standard_id/clause_number/requirement/clause_type/applies_to/created_at）/ `StepMaterial`（id/step_id/catalog_id/usage_type/quantity）/ `StepTool`（id/step_id/catalog_id） |
| **SQLite 迁移** | `ALTER TABLE material_catalog ADD COLUMN specialty VARCHAR(50)` + `ALTER TABLE process_steps ADD COLUMN specialty VARCHAR(50)`（idempotent） |
| **`app/services/document_processor.py`**（process_document :341） | 解析完成后 try-except 调 `KnowledgeExtractor().extract_and_save(str(material_id), db)`（失败记日志不阻塞）；文档名含 QJ903 → `StandardExtractor().extract_and_save(...)` |
| **`app/services/knowledge_search.py`**（去 stub） | 恢复 6 函数真查询（search_materials/search_tools_for_step/search_materials_for_step/search_standard_clauses/get_full_step_context/build_knowledge_context_text）+ ORM import |
| **extract_and_save 维度传递** | KnowledgeExtractor.extract_and_save 落 MaterialCatalog/ProcessStep 时从 Material 行带 model/specialty |

## 禁区

- ❌ extract_and_save 的 relations（StepMaterial/StepTool 关联落库）——补 ORM 不扩展落库
- ❌ Step 3 画像 / Step 4 标准 review
- ❌ 改 source-driven 主路径 / KnowledgeExtractor 抽取逻辑 / 异步队列 / 前端

## 验证

1. ORM：`python -c "from app.models.database import MaterialCatalog,ProcessStep,Standard,StandardClause,StepMaterial,StepTool; print('OK')"`
2. 迁移：PRAGMA 确认 material_catalog/process_steps 有 specialty 列
3. 落库：`KnowledgeExtractor().extract_and_save('1', db)` → material_catalog/process_steps 新增行 + 维度写入
4. C 查询：`KnowledgeSearchService().search_materials("螺钉")` 返回真实数据
5. 标准：`StandardExtractor().extract_and_save(...)` → standards/standard_clauses 落库
6. 触发：document_processor 解析 PDF → 自动 extract（日志）
7. pytest 回归不引入新 fail

## 拆分（执行 loop 节点）

1. **节点1 补 6 ORM + 维度列迁移**：database.py 6 类 + ALTER TABLE specialty
2. **节点2 extract_and_save 维度传递**：落库从 Material 带 model/specialty
3. **节点3 document_processor 接触发**：:341 try-except KnowledgeExtractor + StandardExtractor
4. **节点4 C 恢复查询**：knowledge_search 6 函数去 stub
5. **节点5 验证**：extract_and_save('1') 实测 + C 查询 + pytest
