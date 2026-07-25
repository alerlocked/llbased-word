# 需求对齐卡：后端 filled_data 空 · 治根

## 背景（bug 怎么来的）
mock 定位（2026-07-25 frontend-display-debug）：**前端渲染链 OK**（mock template_data → 渲染 table + 数据行 "测试内容"）。bug 在**后端**：实际生成 `structured_results[code].filled_data` 空 → `template_data` 的 8 chapters 都是空壳 → 前端渲染空表格（无数据行）→ 用户"不显示"。

filled_data 链路（Grep 确认）：
1. `writing_agent.py` 产 filled_data（:303-322 LLM JSON 解析 / :1246-1290 chapter_data.filled_data）
2. `orchestrator.py` merge（:985-987 `inner["filled_data"] = merged`）
3. `orchestrator.py` 构造 structured_results（:3147-3162 `structured_results[code] = inner`）
4. `agent.py:1128` 组装 ChapterData（`filled_data=data.get("filled_data", [])`）

pitfalls §2（结构化断路）高度相关。

## 目标
从后端**治根** filled_data 空（填充，template_data 有数据，前端显示）。

### 成功标准（可观察）
- 生成后 `template_data.chapters[*].filled_data` **有数据**（非空）。
- playwright 验证：前端表格显示数据行（不空）。
- 不回归：pytest + 其他章节正常。

## 边界

### 做
- 定位 filled_data 空点（writing_agent 产 / orchestrator merge / 构造 哪环丢）。
- 治根（填 filled_data）。
- playwright 验证（前端显示）。

### 不做
- 不动前端（渲染链 OK，已 mock 证）。
- 不动 enable_thinking / thinking_budget（已治慢）。
- 不重写生成架构。

## 模糊点（进 PlanMode 定）
1. filled_data **为什么空**（LLM 返回空 JSON / merge 丢 / 构造没填 / 某章节类型如 G25a per-step 不走 filled_data）？
2. filled_data 该填什么（各章节类型：G25a 工序行 / G18a 配套 / G4a 目录 各字段）？

## 下游
- → PLAN（同 slug `backend-filled-data-fix`）
