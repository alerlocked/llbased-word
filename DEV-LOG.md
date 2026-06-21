---
project: localknowledgebase-word
path: D:/Project Nantianmen/projects/localknowledgebase-word
branch: main
updated_at: 2026-06-22T00:14:11+08:00
last_commit: c7b18b2
status: content-detail（G25a content 详实化:extract colspan 修复+生成展开+开头说明,PLAN c7b18b2 seal 执行中）
task_state: running
task_slug: content-detail
---

<!--AUTO:GIT-->
## 最近变更
- `c7b18b2` plan(content-detail): extract colspan fix + gen expand + assembly overview (0 seconds ago)
- `8125c3e` chore(content-quality): wrap up done — node B baseline + node A tighten 38->5 (67 minutes ago)
- `fab6783` feat(g25a): tighten inspection count (38->5, global cap <= ops) (73 minutes ago)
- `c603273` feat(diag): all-chapter generation probe (81 minutes ago)
- `57bb7be` chore(devlog): task_state running for content-quality (2 hours ago)
- `5749974` plan(content-quality): G25a inspection tighten + all-chapter diagnose probe (2 hours ago)
- `dc0537f` chore(contract-align): wrap up done — 3 nodes complete (3 hours ago)
- `2b2b009` feat(g25a): turn inspection into process rows (post-merge expand, per-step parallel untouched) (4 hours ago)
- `34f4520` chore(devlog): task_state running for contract-align (4 hours ago)
- `8e98923` plan(contract-align): G25a inspection-row + frontend-backend column-key guard + docx2pdf fix (4 hours ago)
<!--/AUTO:GIT-->

## 当前状态
- **在做**：content-detail —— G25a content 详实化。根因=_table_to_markdown 不展开 colspan(op5 工步被吞 extract 仅9字)+ step_msg 概括 + 开头说明缺。节点1 colspan 展开(核心前置)→ 节点2 生成详实 → 节点3 开头说明
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
