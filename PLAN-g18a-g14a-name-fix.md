# PLAN: G18a 配套表名称用 catalog 配对（修复 derive 倒推错位+待补）

> slug: `g18a-g14a-name-fix` · 承接 `ALIGN-g18a-g14a-name-fix.md` · seal 后不可变，进度记 DEV-LOG/git

## Context

Web 端验收 project=2 发现 G18a 配套明细表**代号-名称错位 + 名称待补**（56 处待补集中在 G18a/G14a）。诊断到根因：

`orchestrator.py:_derive_strong_node`（895-968）对列表表调 `_merge_derived_rows(inner["filled_data"], derived_rows, slot_keys)`（984-1007），按**行索引 i** zip 两条数据：
- `original` = Phase3 structured 直填（代号-名称配对正确）
- `derived_rows` = 从 G25a 倒推（**行顺序不同，零件不同**）
- `if not merged[i].get(k): merged[i][k] = v` → 当 original[i] 的 part_name 空，用 derived[i]（另一个零件）的 part_name 填 → **错位**（KA6-0-KZD 配了"行程延时开关组合"实为六舱）
- 倒推也没有的 → 末尾标"待补"（KA6-20-KZD 待补，但 material_catalog 有"尾焰挡板组件"）
- **全程不查 material_catalog**（extract 已有正确配对，source-driven-fix 达标）

修复：G18a merged 后按 part_code exact 查 material_catalog.name 覆盖错位值+补待补。

**G14a 经诊断不是 bug，本期不修**：辅料 catalog `standard_code=None`（knowledge_extractor.py:572）无法按代号 exact 查；G14a 待补字段是定额（per_set_quota/batch_quota，derive-strong-node 字段边界，设计性）。范围收敛到 G18a。

## 改动清单

| 文件 | 改什么 |
|------|--------|
| `backend/app/services/knowledge_search.py` | 新增 `find_material_by_code(db, code)`：exact `MaterialCatalog.standard_code == code` `.first()`，返回 dict 或 None。**不复用 search_materials**（LIKE 误匹配 KA6-0-KZD↔KA6-011-KZD） |
| `backend/app/agents/orchestrator/orchestrator.py` | ① 新增 `_enrich_names_from_catalog(rows, code_key, name_key, chapter_code)`：`SessionLocal()` 查 catalog，按 code exact 查，命中则**覆盖** name（原地改）。② `_derive_strong_node` single_row_list 分支（959-968）`inner["filled_data"]=merged` 后，仅 `if code=="G18a"` 调用 enrich |
| `backend/tests/test_knowledge_search.py` | 新增 TestFindMaterialByCode（exact 命中 / 空 code / 查不到 / 不误匹配子串） |
| `backend/tests/test_orchestrator_derive.py` | 追加 TestEnrichNamesFromCatalog（覆盖错位值 / 填待补 / catalog miss 保留原值 / 跳过空 code+待补 / 空 rows noop / db 失败不 raise） |

## 复用现有

- `KnowledgeSearchService._material_to_dict`（knowledge_search.py）行转 dict
- `SessionLocal`（app/database.py:19）db session，模式参考 writing_agent.py:1678（`db=SessionLocal()` + try/finally close）
- `MaterialCatalog` ORM（database.py:376，standard_code/name 字段）

## 覆盖策略

catalog 查到 name → **无条件覆盖** merged part_name（含 Phase3 structured 值）。理由：catalog 是 extract 结构化 code→name 配对，与 Phase3 同源但配对确定性更高；错位 bug 根因正是倒推值污染，需 catalog 覆盖纠错。catalog miss（code 查不到）→ 保留原值（不破坏）。code 为空或"待补" → 跳过。GB/T68-2000 等重复代号 `.first()` 取首条（name 带规格区分，填名称够用）。

## G14a（本期不修，说明）

- 辅料 catalog `standard_code=None`（knowledge_extractor.py:572 硬编码），按 component_code exact 查不到
- 待补字段是定额（per_set_quota/batch_quota），derive-strong-node 字段边界明确"推不了"，设计性待补
- 保留现状，不算 bug。后续若要补 material_desc 需另设计按 name 模糊匹配（不在本期）

## 禁区

- extract 层（knowledge_extractor.py / structured_extractor）
- G25a/G22a/G19a 倒推逻辑（writing_agent `_derive_list_from_upstream`/`_provenance_filter`）
- `_merge_derived_rows` 通用逻辑（984-1007）
- derive-strong-node 架构（_derive_strong_node 整体流程、LIST_CHAPTERS、dual_list 分支 945-958）
- G14a / dual_list 分支
- orchestrator.py:2095/2396/2413 死代码 `from app.models.database import get_db`（错误导入，不顺手改）

## 验证

1. `cd backend && python -m pytest tests/test_knowledge_search.py tests/test_orchestrator_derive.py -v`（全绿）
2. catalog 抽查：`find_material_by_code(db,'KA6-20-KZD')`→尾焰挡板组件、`'KA6-0-KZD'`→六舱（非 None、非 KA6-011-KZD 误匹配）
3. Web 回归：project=2 生成，G18a filled_data 的 KA6-20-KZD part_name=尾焰挡板组件（非待补）、KA6-0-KZD part_name 与代号配对正确（非"行程延时开关组合"错位）。产物入 `.test-runs/g18a-g14a-name-fix/`

## 节点拆分（执行 loop）

1. **节点1**：`find_material_by_code` + 单测（commit `feat`）
2. **节点2**：`_enrich_names_from_catalog` + 单测（commit `feat`）
3. **节点3**：G18a 分支接入 + 全量回归 + web 验收（commit `fix`）

## 执行约定

- seal：本文件 git commit `plan: g18a-g14a-name-fix seal`
- 业务代码简单直接改（每节点 1-2 文件）
- 进 loop 第一件事 `/devlog-update localknowledgebase-word` 写 running + task_slug
- 出错暂停（lead.md 第 6 步），不硬撑
