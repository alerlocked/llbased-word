---
project: localknowledgebase-word
path: D:/Project Nantianmen/projects/localknowledgebase-word
branch: main
updated_at: 2026-07-05T14:20:01+08:00
last_commit: bd7c1c7
status: derive-strong-node 执行中（节点1：升级 _derive_list_from_upstream 溯源+字段边界）
task_state: running
task_slug: derive-strong-node
---

<!--AUTO:GIT-->
## 最近变更
- `bd7c1c7` refactor(writing): remove weak 三空 derivation fallback (节点3) (0 seconds ago)
- `105f248` feat(orchestrator): derive strong node + merge helpers (节点2) (2 minutes ago)
- `49645a1` feat(writing): provenance filter for _derive_list_from_upstream (节点1) (8 minutes ago)
- `7bab17d` plan: derive-strong-node (倒推强节点) seal (12 minutes ago)
- `885fc7d` test: refine file-level xfail to method-level (kill 149 xpass noise) (2 hours ago)
- `418111b` fix(test): repair fixtures causing 13 setup/teardown errors (2 hours ago)
- `e3377e2` test: xfail mineru 3.x suite + single-point edge failures (level-3 final) (3 hours ago)
- `97bc969` test: xfail refactor-stale suites to quiet false-red noise (level-3 remainder) (3 hours ago)
- `7b8b308` test: xfail review engine gaps + hybrid_parsing stale (level-3) (3 hours ago)
- `e2ab5db` fix: table_merger continuation logic + LongTermMemory pydantic + review API (level-3) (3 hours ago)
<!--/AUTO:GIT-->

## 当前状态
- **在做**：derive-strong-node（倒推强节点）—— 节点1✅ _provenance_filter + 节点2✅ orchestrator `_derive_strong_node` 强节点 + 节点3✅ 移除 writing_agent.py:1161-1203 旧三空兜底（替换，归强节点；parsed 守 None 下游 if 守卫安全）+ 12 单测稳。当前节点4：documents/1 全链路验收（行数对比+人工抽样+待补检查+pytest 回归）。进度 3/4。
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
