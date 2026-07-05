---
project: localknowledgebase-word
path: D:/Project Nantianmen/projects/localknowledgebase-word
branch: main
updated_at: 2026-07-05T21:32:32+08:00
last_commit: 3015abc
status: cleanup-and-dimensions 执行中（节点1：清噪删死壳）
task_state: running
task_slug: cleanup-and-dimensions
---

<!--AUTO:GIT-->
## 最近变更
- `3015abc` feat(db): Material 加 model/specialty 维度（节点2） (0 seconds ago)
- `4dedab9` refactor: 检索清噪删死壳（节点1） (14 minutes ago)
- `9fe326e` plan: cleanup-and-dimensions (检索清噪+型号专业维度 Step 0+1) seal (51 minutes ago)
- `b5da812` chore(devlog): derive-strong-node done (代码完成，web 验收待用户) (6 hours ago)
- `8cf1719` fix(test): autouse mock.patch.stopall + GC between tests (draft flaky 根治) (6 hours ago)
- `1e6dd1d` fix(test): snapshot/restore registry around test_registry clear (隔离修复) (7 hours ago)
- `bd7c1c7` refactor(writing): remove weak 三空 derivation fallback (节点3) (7 hours ago)
- `105f248` feat(orchestrator): derive strong node + merge helpers (节点2) (7 hours ago)
- `49645a1` feat(writing): provenance filter for _derive_list_from_upstream (节点1) (7 hours ago)
- `7bab17d` plan: derive-strong-node (倒推强节点) seal (7 hours ago)
<!--/AUTO:GIT-->

## 当前状态
- **在做**：cleanup-and-dimensions（检索清噪+型号专业维度 Step 0+1）—— 节点1 清噪（删 SearchAgent/IndexingService/UnifiedRetrieval/KnowledgeGraph/vector_store 死壳 + writing_agent:148 改调用 + C knowledge_search stub）。PLAN seal @9fe326e。进度 1/6。
- **完成**：derive-strong-node（倒推强节点）—— 节点1✅ `_provenance_filter`（溯源校验，丢弃 G25a 无出处条目）+ 节点2✅ orchestrator `_derive_strong_node`（generated_chapters 后/Review 前无条件倒推，原文优先合并 + 待补标注）+ 节点3✅ 移除 writing_agent 三空弱兜底 + 节点4✅ pytest 全量回归 0 failed（683 passed）。**附带修复测试隔离**：test_registry snapshot/restore（registry 全局单例 clear 不恢复）+ conftest autouse `mock.patch.stopall+GC`（根治 draft_service 跨测试 async mock 残留 flaky）。**documents/1 web 验收待用户**（行数对比+抽样核对 G25a 出处+待补字段）。
- **完成**：content-detail —— G25a content 详实化三节点全过。① 节点1 _table_to_markdown colspan 网格展开(extract op5 9→729字/ASM 1134→4992,三层根因)② 节点2 生成 prompt 详实化(content_avg 32→461字,零臆造)③ 节点3 装配卡说明(extract_assembly_overview 769字+注入)。待用户 web 验证;后续重跑 diagnose_all_chapters 看其他章节是否受益 + G14a/G12a 逐章
- **历史完成**：content-quality(检验收紧38→5+实证) + contract-align(检验行+契约guard+docx2pdf)
- **历史完成**：contract-align（检验工序行+契约guard+docx2pdf中文路径）三节点全过
- **节点A✅**：G25a 检验工序行（方案Y merge 后处理）。LLM 照常生成 content+inspection，_expand_inspection_rows 拆检验行插入；模板删 inspection 列。diagnose 40rows=10操作+30检验，检验行 step_name=检验，复杂工序多点/简单单点。commit 2b2b009
- **节点B✅**：前后端 column-key 契约校验 guard（scripts/hooks/guard-column-align.py，PostToolUse warn）。对比模板 key vs layout key，G10a/G14a/G12a 白名单，dual_list/flow_chart 跳过，路径过滤。3 项验证过。父 repo e2d5b28
- **节点C✅**：docx2pdf 修复。根因=Word COM 对中文路径 Open 卡死；解法=staging 到 ASCII temp dir + win32com 优先。中文路径端到端 PDF 306KB 产出。父 repo 709b624
- **待用户**：web 端 project=2 装配卡刷新确认检验行渲染（后端 diagnose 已实证 filled_data 含检验行）
- **历史**：g25a-perstep 已完成（A✅B✅C✅ web 验证）；g25a-write 已落地

## 关键决策
- **G25a 检验=单独工序行（用户定+截图验证）**：检验不单独成列（前端不加列），后端生成检验工序行（step_name=检验），贴合真实工艺文件格式。方案Y（merge 后处理）不动 g25a-perstep 并行核心
- **前后端契约校验=guard hook（用户定）**：PostToolUse warn 脚本对比模板 key vs layout key；G10a/G14a/G12a 历史不一致白名单兜底（KNOWN_DIFFS），本次不修，TODO 单独排期
- **docx2pdf 中文路径=Word COM 卡死根因**：Word.Application COM Open/SaveAs 对非 ASCII 路径卡死/URL 编码 %20；解法=staging 到 ASCII temp dir 转换再复制出（纯文件复制不怕中文）
- **行文标准=画像两层**（用户定）：principles 强约束 + preferences 偏好
- **参数参考值=triples 兜底**（用户定）：工步原文优先，绝不臆造
