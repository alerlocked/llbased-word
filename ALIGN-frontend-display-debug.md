# 需求对齐卡：前端不显示 bug · playwright 端到端定位

## 背景（bug 怎么来的）
2026-07-25 测试：后端生成完成（writing_task_completed 多章节 + draft_complete success=True），但**前端不显示**。日志关键：
- `[draft_complete] 提取到 new_content 长度=0`（markdown 空）
- `template output: 8 chapters`（structured_results 有）

draft template-first 流程（agent.py:1036）：LLM 生成进 `structured_results`（template 表格），**不进 markdown `new_content`**。前端收到 `editor_content=""`（空）+ `template_data`（8 chapters），但没渲染 / 没显示。

**pitfalls §2（2026-06-01 结构化存储断路）高度相关**："save_content_files 写了 content.json v2 + content.html，但 content API 没改、前端消费不到"——可能就是这个 bug 的根（structured 写了但前端/API 断路）。

## 目标
用 playwright **端到端复现** bug + **定位根因**（后端 SSE 没发对 / 前端没渲染 / content API 断路），给修复方向。

### 成功标准（可观察）
- playwright 复现：触发生成 → 前端 DOM 不显示（或显示空）。
- 定位根因：抓 generate-stream SSE（发了 `template_data` 没 / `editor_content` 空不空）+ 前端 DOM（渲染没）+ content API（返回啥），指明**哪一环断**。
- 修复方向：基于根因给（改 SSE 发送 / 改前端渲染 / 改 content API），带文件 + 行号。

## 边界

### 做
- playwright 起前端 + 触发生成（project=2）+ 抓 SSE + DOM + content API。
- 定位根因（后端 SSE / 前端渲染 / content API 哪断）。
- 给修复方向（文件 + 行号）。

### 不做
- 不重写 template / 前端架构。
- 不动 enable_thinking / thinking_budget（已治慢，不动）。

## 模糊点（进 PlanMode 前对齐）
1. **playwright 范围**：完整端到端（真 LLM 生成，慢/可能限流）vs mock SSE（造 `template_data` 测前端渲染，快）？推荐 mock 先定位前端 vs 后端，必要再真生成。
2. **起服务**：前端 dev（npm run dev :3000）+ 后端（python main.py :8000）我起？还是你已起（我只 attach playwright）？
3. **定位后改不改**：只定位 + 报告（用户另开 lead 修）vs 定位 + 小修（根因明确就改）？

## 下游
- → 进 PLAN（同 slug `frontend-display-debug`）
