---
project: localknowledgebase-word
path: D:/Project Nantianmen/projects/localknowledgebase-word
branch: main
updated_at: 2026-07-05T10:43:38+08:00
last_commit: df0946d
status: content-detail 完成（G25a content 详实化:extract colspan 修+生成详实+开头说明,content 32→461字）
task_state: done
task_slug: content-detail
---

<!--AUTO:GIT-->
## 最近变更
- `df0946d` fix(test): clean stale tests after refactor (level-2) (0 seconds ago)
- `c188f70` chore(test): upgrade pytest-asyncio 1.4.0 + register markers + remove orphan tests (9 minutes ago)
- `c0a7e83` fix(logging): rename LogRecord reserved attrs in structured logger kwargs (15 minutes ago)
- `8687cfd` fix: backport state-machine + memory NoneType + vite dead-ref from kylin (25 hours ago)
- `69d4dd1` feat: fix batch-upload/upload-folder material_id + buffer API (4 days ago)
- `8a52846` plan: fix batch-upload/upload-folder material_id + buffer API (4 days ago)
- `9161535` chore: remove dead code (diagnose scripts, unused services/components) (8 days ago)
- `7326484` perf(vl_service): lazy-load mineru model to stop hot-reload reloads (9 days ago)
- `e4c31ba` perf(mineru): batch VLM extraction + fix misleading config comments (9 days ago)
- `016ecd3` chore(content-detail): wrap up done — content 32->461, op5 9->729 (13 days ago)
<!--/AUTO:GIT-->

## 当前状态
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
